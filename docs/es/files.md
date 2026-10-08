# Qué es cada archivo

[← README](../../README.es.md) · [English](../files.md) · Español

Cada archivo y carpeta del repositorio: qué hace, para qué sirve y qué representa.

## Raíz

| Archivo | Qué es |
| --- | --- |
| `README.md` / `README.es.md` | Punto de entrada: qué es el proyecto, la arquitectura y por dónde empezar (inglés / español). |
| `common.yaml` | La configuración compartida. Terraform lee `project` (tags y nombres); el pipeline y el reviewer leen `backend`, `ai` y `terraform` (`accounts`, `deploy` y los opcionales `roots`, `modules`, `protected`, `conventions`). Es el único lugar que un equipo edita para adaptar la plataforma a sus cuentas. |
| `.terraform-version` | La versión de Terraform para herramientas como tfenv (los workflows fijan `~> 1.16.0`). Un cambio en él marca todas las raíces como "afectadas". |
| `.tflint.hcl` | Configuración de TFLint: los conjuntos de reglas de Terraform y AWS y las reglas activas (versión requerida y providers, variables y outputs documentados y tipados, nombres). |
| `.claude/agents/terraform-ia-engineer.md` | El asistente del proyecto para Claude Code: sabe cómo se construyen aquí los módulos, las reglas, el código del reviewer y la documentación. Propone y espera tu aprobación, nunca ejecuta comandos y te da los comandos git para que los ejecutes tú. |
| `tools/pyproject.toml` | Configuración de `ruff` y `mypy`, que el job `python` de cada PR ejecuta sobre el Python del reviewer. |
| `.gitignore` | Deja fuera el state, los planes, el entorno de Python, el `backend.tf` que genera el pipeline y el historial del editor. |

## `.github/workflows/`: el pipeline

| Archivo | Qué hace |
| --- | --- |
| `pull-request.yml` | Se ejecuta en cada pull request. Descubre las raíces y los módulos afectados, ejecuta `fmt`, los checks de Python (ruff, mypy), `validate`, TFLint, Checkov y el contrato del repositorio, pide a `terraform.yml` un plan de solo lectura de cada raíz afectada y arma el comentario de revisión. Un PR hacia producción omite esos seis checks y ejecuta solo plan, costo y revisión. |
| `terraform.yml` | El único workflow que toca AWS. Para una raíz elige las llaves de la rama, verifica la cuenta, comprueba el bucket de state y ejecuta `init` → `plan` → (`apply`). Lo llaman los PR para un plan, lo dispara un push a `develop` o `main` para un apply, o se inicia a mano. |

## `tools/reviewer/`: el reviewer

Un paquete de Python que ejecutan los workflows: cada paso llama a su propio archivo, por ejemplo `python -m reviewer.ci.terraform_init`. Su única
dependencia es PyYAML. La calidad de su código se exige en cada PR con el job `python`: `ruff` (errores, imports, bugs probables) y `mypy` (tipos), configurados en `tools/pyproject.toml`. Cada carpeta es un tema:

```
lib/git_diff → qué cambió  ─►  terraform/ → qué afecta  ─►  rules/ → qué reglas rompe
                                                               │
                       review/ → veredicto y comentario del PR  ◄──┘        ai/ → resumen opcional
```

| Carpeta / archivo | Qué es |
| --- | --- |
| `ci/` | Lo que ejecutan los workflows, un archivo por paso. |
| `terraform/` | Entender el código de Terraform y el plan. |
| `rules/` | El contrato: el catálogo de reglas y el código que las comprueba. |
| `review/` | La revisión en sí: el veredicto y el comentario del PR. |
| `infracost/`, `aws/`, `versions/` | Leer los datos de Infracost; comprobar a qué cuenta AWS pertenecen las llaves; buscar versiones nuevas de Terraform y de los providers. |
| `ai/` | El resumen opcional de IA. |
| `chat/` | Un chat en la terminal con Gemini que responde preguntas sobre el proyecto a partir de su documentación (`terminal_chat.py`) y, con `/reviews`, a partir de los comentarios de review de los PR recientes: planes, costos, versiones y hallazgos por fecha (`pr_reviews.py`, se leen con `gh`). `format_terminal.py` da formato a las respuestas (instala `rich` para ver tablas). Solo lectura: sin archivos, comandos ni AWS. Se ejecuta a mano con tu propia `GEMINI_API_KEY`: `PYTHONPATH=tools python -m reviewer.chat.terminal_chat`. |
| `lib/` | Utilidades que puede usar cualquier carpeta y que no son pasos de workflow: `git_diff.py` (los archivos que cambia un PR: `git diff base...HEAD`, solo cambios confirmados en commits), `github_actions.py` (escribe `$GITHUB_OUTPUT` y `$GITHUB_STEP_SUMMARY`, reporta errores, indica el modo y la rama) `workflow_jobs.py` (los jobs de la ejecución actual con un enlace a cada uno, para el comentario) y `redact_secrets.py` (oculta credenciales en el texto y los valores que recibe la IA). |

### `terraform/`: entender el código de Terraform y el plan

| Archivo | Qué hace |
| --- | --- |
| `read_tf_files.py` | Lee un archivo `.tf` y encuentra sus bloques (`resource`, `module`, `variable`...) y sus atributos. |
| `terraform_map.py` | El mapa del repositorio: qué carpetas son raíces y cuáles módulos, qué módulo llama a cuál, y cuáles afecta un conjunto de archivos modificados. También lee el bloque `terraform:` de `common.yaml`. |
| `affected_roots.py` | Sobre qué raíces actuar para una rama destino (aplicando `terraform.deploy`). La decisión en la que se apoyan los workflows. |
| `read_plan_json.py` | Lee el plan (`terraform show -json`) y lo reduce a conteos y cambios saneados, sin state, valores de variables ni secretos. |
| `run_terraform.py` | El único lugar que inicia el programa `terraform` en una carpeta. No sabe nada de GitHub ni de AWS. |

### `rules/`: el contrato

| Archivo | Qué hace |
| --- | --- |
| `rules.yaml` | El catálogo: una entrada por regla (id, severidad, título, explicación, parámetros). La única fuente de verdad. |
| `code_rules.py` | Las reglas que leen los archivos `.tf`: `MODULE-*`, `TAGS-*`, `ROOT-*` y `COST-001`. |
| `plan_rules.py` | Las reglas que leen el plan y la estimación de costo: `PLAN-001` y `COST-002`. |
| `registry.py` | Conecta el nombre `check:` de una regla con su función, construye los hallazgos y ejecuta las reglas del plan. |

La lista de reglas está en [Los checks](checks.md).

### `review/`: la revisión en sí

| Archivo | Qué hace |
| --- | --- |
| `finding.py` | La forma de un hallazgo (severidad, evidencia, archivo, línea, regla...) que devuelve cada regla, y el orden de severidades. Es el formulario que una regla llena para reportar un problema; no dice cómo deben construirse los módulos (eso es el [estándar de módulos](module-standard.md)). |
| `run_review.py` | Una revisión, en orden: raíces afectadas, hallazgos, el veredicto determinista y el resumen opcional de IA. |
| `render_pr_comment.py` | Construye el texto del comentario del PR (Markdown) a partir del resultado de una revisión: ocho secciones, desde el resumen de IA hasta la decisión. |

### `infracost/`, `aws/` y `versions/`: los datos de costo, la cuenta AWS y las versiones

| Archivo | Qué hace |
| --- | --- |
| `infracost/read_infracost_json.py` | Lee el resultado de Infracost y lo reduce a totales, la variación mensual, el costo por recurso y lo que no se pudo valorar. Nunca ejecuta Infracost ni estima un precio: los precios salen solo de aquí. |
| `versions/latest_versions.py` | Busca las últimas versiones de Terraform y de los providers (el chequeo de versiones de HashiCorp y el Terraform Registry), las compara con las que usó el plan y entrega el enlace a las notas del lanzamiento. Solo informa: nunca cambia un archivo ni el veredicto, y si una consulta falla el comentario lo indica. |
| `aws/account.py` | Elige las llaves AWS de una rama, le pregunta a AWS a qué cuenta pertenecen y comprueba que exista el bucket de state. |

### `ci/`: un archivo por paso de los workflows

Cada archivo es el código que ejecuta un paso. Lee las variables de entorno que le pasa el workflow, pregunta qué raíces y módulos afecta
el PR, ejecuta la herramienta y devuelve lo que el workflow necesita (outputs del paso, el resumen del job, el comentario). El nombre es el
del paso que ves en GitHub.

| Archivo | Paso | Qué hace |
| --- | --- | --- |
| `discover_roots.py` | affected configurations | Las raíces que afecta un PR y que su rama destino posee: entrega al workflow la matriz para los jobs de plan, cuántas son y la lista con los motivos. |
| `select_roots.py` | which roots (terraform.yml) | Las raíces sobre las que actúa una ejecución de `terraform.yml`: las que afectó un push, o la que se pidió. |
| `contract_check.py` | repository contract | Las reglas que leen el código, sobre todo el repositorio; falla ante cualquier hallazgo High o Critical. |
| `terraform_validate.py` | terraform validate | `terraform validate` en los módulos y raíces que afecta un PR, con una caché de providers compartida. |
| `terraform_tflint.py` | TFLint | TFLint, con el `.tflint.hcl` del repositorio, sobre los módulos afectados. |
| `terraform_checkov.py` | Checkov | Checkov sobre los módulos afectados; publica la cantidad de hallazgos. |
| `terraform_init.py` | terraform init | Elige las llaves AWS de la rama, comprueba su cuenta contra `terraform.accounts`, comprueba el bucket de state y luego ejecuta `terraform init`. |
| `terraform_plan.py` | terraform plan | `terraform plan` de una raíz, guardado en `tfplan`. |
| `terraform_show_json.py` | terraform show -json | El plan guardado como JSON (`terraform show -json`) reducido a un resumen saneado que lee la revisión. El plan sin procesar nunca se escribe en disco. |
| `terraform_versions.py` | terraform versions | Registra qué versiones de Terraform y de providers usó el plan, en `versions-<slug>.json`. Es informativo: nunca hace fallar el job. |
| `infracost_estimate.py` | infracost | La estimación de Infracost del plan, escrita en `cost-<slug>.json`. Decide por sí mismo si corre (solo con un plan y solo con una llave de Infracost) e instala la versión fijada de Infracost, verificando su checksum, si la máquina no la tiene. |
| `terraform_apply.py` | terraform apply | Aplica el plan guardado. No hace nada cuando la ejecución es solo un plan. |
| `pr_review.py` | PR comment | Reúne los resultados de los checks, planes y costos, ejecuta la revisión y escribe el texto del comentario. Nunca hace fallar el job. |
| `pr_comment.py` | PR comment | Crea o actualiza el único comentario del PR mediante la API de GitHub. |

### `ai/`: la capa opcional

| Archivo | Qué hace |
| --- | --- |
| `summary.py` | El paso de IA: construye el payload saneado, llama al modelo, valida la respuesta contra el esquema y verifica el texto. Corre solo después de que el veredicto es definitivo. |
| `client.py` | Habla con Gemini por su API REST detrás de una interfaz de un solo método. Reintenta los errores temporales. |
| `grounding.py` | Contrasta con la evidencia cada dirección de Terraform, ruta de archivo y monto en dólares del texto del modelo; lo que no se puede verificar se reemplaza por `<unverified …>`. |
| `prompt.md` | El prompt de sistema: qué recibe el modelo, qué puede y qué no puede hacer, y la forma del resumen. |
| `schema.json` | El contrato de la respuesta: un solo campo, `summary`. |

## `modules/`: capacidades AWS reutilizables

Cada módulo tiene los mismos archivos: `versions.tf` (restricciones de Terraform y de providers), `variables.tf` (entradas tipadas y validadas), `main.tf` (recursos), `locals.tf` (nombres y tags), `outputs.tf` y `README.md`. Las reglas están en el [estándar de módulos](module-standard.md).

| Módulo | Qué crea |
| --- | --- |
| `vpc` | Una VPC con capa privada, capa pública opcional, tablas de rutas por zona, NAT opcional y un endpoint gateway gratuito de S3. |
| `security-group` | Un security group de mínimo privilegio con un recurso por regla; sin reglas y sin egress por defecto. |
| `iam` | Un rol IAM con política de confianza, políticas administradas e inline y un perfil de instancia opcional. |
| `s3` | Un bucket privado, cifrado y con versionado, con política solo TLS y reglas de ciclo de vida opcionales. |
| `aurora` | Un cluster Aurora, PostgreSQL o MySQL (lo elige la entrada `engine`). |
| `lambda` | Una función Lambda con su log group, conexión opcional a VPC, cola de mensajes fallidos y trazado. |
| `eventbridge` | Reglas y destinos de EventBridge en el bus por defecto o uno propio, con reintentos, cola de mensajes fallidos y permisos de invocación. |
| `api-gateway` | Una HTTP API con integraciones Lambda y privadas (VPC Link), logs de acceso y limitación de tráfico. |
| `elb/alb` | Un Application Load Balancer: listeners HTTP/HTTPS, reglas de reenvío, redirecciones, WAF y logs de acceso opcionales. |
| `elb/nlb` | Un Network Load Balancer con target groups y listeners. |
| `ec2/launch-template` | Un launch template endurecido (IMDSv2, volumen raíz cifrado), compartido por `ec2/instances` y `ec2/asg`. |
| `ec2/instances` | Una o más instancias EC2 independientes a partir de un launch template, privadas por defecto. |
| `ec2/asg` | Un Auto Scaling Group sobre un launch template, con renovación gradual, propagación de tags y políticas de escalado. |
| `eks/cluster` | Un plano de control EKS: endpoint privado por defecto, access entries, logs, cifrado de secrets opcional y un provider IRSA. |
| `eks/node-group` | Node groups administrados de EKS, expresados como intención. |
| `eks/addons` | Add-ons administrados de EKS, instalados solo cuando se listan. |

## `infra-example/`: configuraciones raíz construidas con los módulos

Una capa web en una VPC: un Application Load Balancer delante de un Auto Scaling Group de instancias, con Aurora detrás. `dev/web-demo` y `prod/web-demo` son dos raíces con su propio state; comparten el código y difieren en `inputs.yaml`, más la política de producción que aplica `main.tf`.

| Archivo | Qué es |
| --- | --- |
| `main.tf` | Lee `common.yaml` e `inputs.yaml` en `locals` y los valida con preconditions (claves obligatorias, nombre de carpeta, subredes por zona, la política de producción). |
| `network.tf` | La VPC y los tres security groups (balanceador, aplicación, base de datos). |
| `database.tf` | El cluster Aurora. |
| `load_balancer.tf` | El Application Load Balancer, el target group y el listener. |
| `web.tf` (`ec2.tf` en prod) | El rol de las instancias, el launch template y el Auto Scaling Group. |
| `outputs.tf` | Los valores que expone la raíz (nombre DNS, endpoints, ARN del secret, resumen). |
| `inputs.yaml` | Los valores de esta raíz: tags, red, reglas de seguridad, base de datos, balanceador, cómputo. El único archivo que difiere entre dev y prod en intención. |
| `web-user-data.sh.tftpl` | El script de arranque de las instancias web (un servidor web de ejemplo con `/health`). |
| `README.md` (en `infra-example/`) | Las notas propias del ejemplo: estructura, referencia de `inputs.yaml`, qué se comprueba y notas de diseño. |

## `docs/`

| Archivo | Qué es |
| --- | --- |
| `install.md` | Instalación, desde un repositorio vacío hasta el primer PR. |
| `architecture.md` | Cómo funcionan el descubrimiento, las ramas y cuentas, el state, los pipelines, el reviewer y la frontera de la IA. |
| `module-standard.md` | El contrato que sigue cada módulo. |
| `files.md` | Este archivo. |
| `checks.md` | Cada regla que aplica el reviewer: ID, severidad, qué detecta y dónde vive. |
| `es/` | La misma documentación en español; el inglés es el idioma por defecto. |
| `images/` | `hero.svg` y `architecture.svg`, usados por el README. |
