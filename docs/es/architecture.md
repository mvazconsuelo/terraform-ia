# Cómo funciona

[English](../architecture.md) · Español

![Arquitectura de Terraform-ia](../images/architecture.svg)

1. **Una configuración raíz es la unidad de trabajo:** una carpeta con su propio state, que se planifica y se aplica por separado.
2. **El código decide qué se ejecuta y si un cambio pasa.** El descubrimiento, el veredicto y la verificación de cuenta son deterministas.
3. **La IA solo lee.** Escribe un resumen de la evidencia; no puede cambiar un veredicto ni iniciar nada.

```
lib/git_diff → qué cambió ─► terraform/ → qué afecta ─► rules/ → qué reglas rompe
                                                          │
                      review/ → veredicto y comentario del PR  ◄──┘        ai/ → resumen opcional
```

## Descubrimiento de raíces afectadas

No se asume ningún nombre de carpeta. Las raíces salen de `terraform.roots` (globs) o se infieren: una carpeta que nadie llama como módulo, fuera de la carpeta de módulos, con recursos, módulos, un provider o un backend. Los módulos son las carpetas bajo `terraform.modules` (por defecto `modules`) más cualquier cosa llamada con un `source` local.

`terraform/affected_roots.py` recorre el grafo de llamadas entre módulos desde cada raíz. Una raíz está afectada cuando:

| Causa | Ejemplo |
| --- | --- |
| Cambió un archivo de la raíz | `infra-example/dev/web-demo/network.tf` |
| Cambió un módulo que usa, directamente o a través de otro módulo | `modules/vpc/main.tf` |
| Cambió un archivo compartido que lee (`file()`, `templatefile()` con rutas `../`) | `../shared/policy.json` |
| Cambió `.terraform-version` | todas las raíces |

Los `*.md` no afectan nada. Las raíces no afectadas nunca se inicializan, planifican, validan ni aplican. La misma lógica da los módulos afectados (`Repo.affected_modules`), sobre los que corren `validate`, TFLint y Checkov.

## Ramas y cuentas

| Rama | Llaves (secrets) | Cuenta esperada (variable) |
| --- | --- | --- |
| `main` (producción) | `AWS_ACCESS_KEY_ID_MAIN`, `AWS_SECRET_ACCESS_KEY_MAIN` | `AWS_ACCOUNT_ID_MAIN` |
| `develop` y cualquier otra rama | `AWS_ACCESS_KEY_ID_DEVELOP`, `AWS_SECRET_ACCESS_KEY_DEVELOP` | `AWS_ACCOUNT_ID_DEVELOP` |

La rama elige las llaves (la rama destino en un PR, la rama seleccionada en una ejecución manual). Antes de `init` el pipeline le pregunta a AWS la cuenta de las llaves y la compara con la variable del repositorio de esa rama; si no coincide, falta un secret o falta la variable, la ejecución se detiene antes de tocar nada. Las `roots` de los ambientes de una rama son las raíces que puede planificar, revisar y aplicar, así que una ejecución en `develop` nunca toca raíces de producción aunque compartan módulos.

## State

Un state por raíz: clave `<ruta de la raíz>/terraform.tfstate` en el bucket `<proyecto>-tfstate-<id de cuenta>-<región>`, creado a mano una vez por cuenta y región. El lock es nativo de S3 (`use_lockfile`). El pipeline escribe un bloque `backend "s3" {}` vacío salvo que la raíz declare el suyo, y pasa bucket, clave, región, cifrado y lock a `terraform init`.

## Pipelines

**`pull-request.yml`**: `discover` → `fmt` · `python` (ruff, mypy) · `validate` · `tflint` · `checkov` (módulos afectados) · `tests` · `contract` → `plan` por cada raíz afectada (llama a `terraform.yml`, solo lectura) → `review` (comentario). Un PR hacia la rama por defecto (producción) omite esos seis checks, que ya pasaron en el PR hacia `develop`, ejecuta plan, costo y revisión con las llaves de producción, y marca todas las raíces como protegidas. Los PR de forks no reciben secrets ni IA.

**`terraform.yml`**: lo llaman los PR para un plan de solo lectura, y se ejecuta a mano para planificar o aplicar una raíz (`gh workflow run`). **Fusionar un pull request nunca toca AWS**: desplegar es siempre una ejecución manual y explícita, y solo desde una rama que un ambiente nombre.

Ambos workflows: las actions están fijadas por SHA de commit (Dependabot las mantiene al día), cada job tiene un timeout y un push nuevo a un pull request cancela su ejecución en curso. Un `apply` nunca se cancela: las ejecuciones de una misma raíz hacen fila.

## El reviewer

`tools`: hallazgos de los checks del contrato sobre el código (`rules/rules.yaml` + `rules/code_rules.py`) y de los checks sobre el plan y el costo; luego:

- **Veredicto:** `REQUEST_CHANGES` cuando un hallazgo confirmado es HIGH o CRITICAL o falló un check externo (fmt, ruff y mypy, tests, validate, TFLint, el contrato del repositorio); si no, `PASS`. Por ahora Checkov solo avisa. El riesgo es la mayor severidad encontrada. Un check omitido no es una falla.
- **`PLAN-001`:** un plan que destruye o reemplaza un recurso con estado es CRITICAL en una raíz protegida (todas las raíces en un PR hacia producción) y HIGH en el resto.
- **Comentario:** uno por PR, actualizado en el lugar. El encabezado es un recuadro de color (verde para PASS, rojo o amarillo para REQUEST_CHANGES) con la decisión y el riesgo, y una tabla con el ambiente, la cuenta AWS, el commit revisado y el enlace a la ejecución; luego ocho secciones: resumen de IA con Gemini, configuraciones afectadas, checks, plan de Terraform (con los reemplazos), costo, versiones, reglas del repositorio y decisión. El nombre de cada check y el plan de cada raíz enlazan al log del job que los ejecutó.

- **Versiones:** las versiones de Terraform y de providers que usó el plan, frente a las últimas publicadas, con un enlace a lo que cambió. Solo informa; nunca cambia un archivo ni afecta la decisión. Si los registros no responden, la sección lo indica.

Cada regla, con su severidad y la función que la implementa, está en [Los checks](checks.md).

## Frontera de la IA

Apagada por defecto (`ai.enabled`). Recibe un único payload saneado (veredicto, raíces afectadas, checks, plan, reemplazos, costo, hallazgos, los nombres de los archivos cambiados (nunca su contenido), el texto del PR; nunca el state ni credenciales). Nunca recibe archivos fuente, solo la evidencia anterior, y devuelve un texto validado contra `ai/schema.json`. Cada dirección de Terraform, ruta de archivo y monto en dólares que contiene se contrasta con la evidencia y se reemplaza por `<unverified …>` si no se puede verificar. Sin herramientas, sin sistema de archivos, sin acceso a AWS ni a GitHub. Si está desactivada, falla o el PR viene de un fork, el comentario lo indica y todo lo demás es idéntico.

## Configuración

`common.yaml`:

| Clave | Significado |
| --- | --- |
| `project` | Primera parte del nombre del bucket de state; también se usa en tags y nombres |
| `backend.encrypt`, `backend.use_lockfile` | Se pasan a `terraform init` |
| `ai.enabled` | Activa el resumen de IA |
| `terraform.roots`, `terraform.modules` | Fijan las raíces, o las carpetas de módulos (por defecto `modules`) |
| `terraform.environments.<nombre>` | **Obligatorio.** Una entrada por ambiente: `branch` (la rama que lo despliega) y `roots` (las raíces que le pertenecen). Una raíz toma su tag `environment` de aquí, y un ambiente desplegado desde `main` debe cumplir `POLICY-001`. La cuenta de AWS de cada rama no está acá: es una variable del repositorio (`AWS_ACCOUNT_ID_DEVELOP`, `AWS_ACCOUNT_ID_MAIN`) |

## Mapa del código

Cada archivo y para qué sirve: [Qué es cada archivo](files.md). Cada regla: [Los checks](checks.md).

## Actualización de dependencias (Dependabot)

Los workflows ejecutan código de terceros (GitHub Actions) con tu token y tus secrets, así que no deben quedarse atrás. Dependabot,
configurado en [`.github/dependabot.yml`](../../.github/dependabot.yml), abre **un pull request por semana hacia `develop`** que sube las
versiones de las acciones de los workflows. Nunca fusiona nada y nunca toca Terraform ni las versiones de providers de los módulos.

Cuando llega uno:
- Léelo. Un salto **mayor** (por ejemplo `checkout` de 4 a 7) puede cambiar cómo se comporta el pipeline.
- Los checks de siempre corren sobre él; fusiónalo solo si pasan. Llega a `main` después, como cualquier cambio, con el siguiente PR de release.
- Su comentario dice "AI summary unavailable / `GEMINI_API_KEY` is not set": los PR de Dependabot no reciben los secrets del repositorio.
  El resto de la revisión es válido.
- Comenta `@dependabot rebase` para refrescarlo, o `@dependabot close` para descartarlo.

Aparte, las *Dependabot alerts* del repositorio avisan cuando una dependencia tiene una vulnerabilidad conocida.

## Límites conocidos

- Checkov corre con `--soft-fail` hasta que se revisen sus hallazgos sobre los módulos.
- Infracost puede no poner precio a recursos que no puede resolver en un plan (por ejemplo un Auto Scaling Group cuyo launch template se crea en el mismo plan); la sección de costo lista lo que no pudo valorar.
- Las raíces se aplican en orden de ruta; las dependencias entre raíces no se modelan.
- Producción es la rama por defecto del repositorio.
- Los tests (`tests/`) cubren el reviewer (cada regla, el veredicto, qué raíces alcanza una ejecución, el guard de cuenta, la redacción de secretos) y los módulos que resuelven o validan algo. Se ejecutan solo en el pipeline, sin AWS ni secrets. Lo único que no cubren es el comportamiento de un `apply` real: ese se apoya en `validate`, el plan y las validaciones de los propios módulos.
- La verificación de tags sobre los recursos del plan no se muestra en el comentario; los tags los exige `TAGS-001` sobre el código.

---

[← Anterior: Instalación](install.md) · [README](../../README.es.md) · [Siguiente: Qué es cada archivo →](files.md)
