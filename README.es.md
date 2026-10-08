<div align="center">

<img src="docs/images/brand/hero.svg" alt="Terraform-ia: Terraform Module Engineering Platform" width="100%">

<br>

![Terraform](https://img.shields.io/badge/terraform-%E2%89%A5_1.11-0B0F14?logo=terraform&logoColor=22D3EE&labelColor=0B0F14)
![CI](https://img.shields.io/badge/ci-GitHub_Actions-0B0F14?logo=githubactions&logoColor=22D3EE&labelColor=0B0F14)
![Modules](https://img.shields.io/badge/modules-reusable_AWS-0B0F14?logo=terraform&logoColor=22D3EE&labelColor=0B0F14)
![Review](https://img.shields.io/badge/review-deterministic-0B0F14?logo=python&logoColor=22D3EE&labelColor=0B0F14)
![AI](https://img.shields.io/badge/AI_summary-optional-0B0F14?logo=googlegemini&logoColor=22D3EE&labelColor=0B0F14)

[English](README.md) · Español

**[Instalación](docs/es/install.md)** · **[Cómo funciona](docs/es/architecture.md)** · **[Qué es cada archivo](docs/es/files.md)** · **[Los checks](docs/es/checks.md)** · **[Estándar de módulos](docs/es/module-standard.md)**

</div>

## Qué es

Una plataforma Terraform: una biblioteca de módulos AWS reutilizables, las configuraciones raíz construidas con ellos y un pipeline de pull request que

- encuentra **qué configuraciones raíz afecta un cambio** (incluidas las que solo usan un módulo compartido modificado) y ejecuta Terraform solo para esas,
- hace el plan, estima el costo y revisa el cambio contra el contrato propio del repositorio,
- **decide aprobado o rechazado con código**, y opcionalmente una IA escribe un resumen en lenguaje claro de la evidencia,
- despliega solo cuando lo pides (una ejecución manual; fusionar nunca toca AWS), con **`develop` y `main` asignadas a cuentas AWS distintas**.

No asume nombres de carpeta: funciona igual con `infra/web`, `terraform/networking` o `environments/dev`.

![De un cambio a un despliegue: cambio, checks, revisión, merge y despliegue manual en la cuenta AWS de dev o de prod](docs/images/architecture.svg)

## Puntos clave

| | |
| --- | --- |
| **Descubrimiento de raíces afectadas** | Un grafo de llamadas entre módulos construido con las rutas locales de `source`. Las raíces editadas, los módulos editados (de forma transitiva) y los archivos compartidos editados se traducen a raíces. La documentación no dispara nada. |
| **Rama → cuenta** | `develop` y `main` usan llaves AWS distintas. Antes de `init`, el pipeline compara la cuenta de las llaves con `terraform.accounts` y se detiene si no coinciden. |
| **Veredicto determinista** | `REQUEST_CHANGES` ante cualquier hallazgo HIGH o CRITICAL o un check fallido; si no, `PASS`. La IA nunca participa. |
| **Reviewer** | Reglas (límites de módulos, tags obligatorios, plan y costo contra los estándares) sobre `terraform`, TFLint, Checkov e Infracost. |
| **Resumen de IA** | Un texto validado contra un esquema y verificado: cada recurso, archivo y precio que menciona se contrasta con la evidencia. Apagado por defecto; un modelo que falla nunca cambia el resultado. |
| **Módulos** | Módulos AWS reutilizables, cada uno con su README y entradas tipadas y validadas. |

## Módulos

Cada módulo tiene su propio README con uso, recursos, entradas, salidas, ciclo de vida y costo. El [estándar de módulos](docs/es/module-standard.md) es el contrato que siguen.

| Module | Qué te da |
| --- | --- |
| [`vpc`](modules/vpc/README.md) | VPC con capa privada, capa pública opcional, tablas de rutas por zona, NAT opcional y un endpoint gateway gratuito de S3. |
| [`security-group`](modules/security-group/README.md) | Security group de mínimo privilegio, un recurso por regla; sin reglas y sin egress por defecto. |
| [`iam`](modules/iam/README.md) | Rol IAM con política de confianza, políticas administradas e inline y un perfil de instancia opcional. |
| [`s3`](modules/s3/README.md) | Bucket privado, cifrado y con versionado, con política solo TLS y reglas de ciclo de vida opcionales. |
| [`aurora`](modules/aurora/README.md) | Cluster Aurora, PostgreSQL o MySQL (lo elige la entrada `engine`). |
| [`lambda`](modules/lambda/README.md) | Función Lambda con su log group, conexión opcional a VPC, cola de mensajes fallidos y trazado. |
| [`eventbridge`](modules/eventbridge/README.md) | Reglas y destinos de EventBridge con reintentos, cola de mensajes fallidos y permisos de invocación. |
| [`api-gateway`](modules/api-gateway/README.md) | HTTP API con integraciones Lambda y privadas (VPC Link), logs de acceso y limitación de tráfico. |
| [`elb/alb`](modules/elb/alb/README.md) | Application Load Balancer: listeners HTTP/HTTPS, reglas, redirecciones, WAF y logs de acceso opcionales. |
| [`elb/nlb`](modules/elb/nlb/README.md) | Network Load Balancer con target groups y listeners. |
| [`ec2/launch-template`](modules/ec2/launch-template/README.md) | Launch template endurecido (IMDSv2, volumen raíz cifrado), compartido por `ec2/instances` y `ec2/asg`. |
| [`ec2/instances`](modules/ec2/instances/README.md) | Instancias EC2 independientes a partir de un launch template, privadas por defecto. |
| [`ec2/asg`](modules/ec2/asg/README.md) | Auto Scaling Group sobre un launch template, con renovación gradual, propagación de tags y políticas de escalado. |
| [`eks/cluster`](modules/eks/cluster/README.md) | Plano de control EKS: endpoint privado por defecto, access entries, logs, cifrado de secrets opcional e IRSA. |
| [`eks/node-group`](modules/eks/node-group/README.md) | Node groups administrados de EKS, expresados como intención. |
| [`eks/addons`](modules/eks/addons/README.md) | Add-ons administrados de EKS, instalados solo cuando se listan. |

## Stack

<img alt="Terraform" src="https://img.shields.io/badge/Terraform-844FBA?style=for-the-badge&logo=terraform&logoColor=white">&nbsp;<img alt="AWS" src="https://img.shields.io/badge/AWS-232F3E?style=for-the-badge&logo=amazonwebservices&logoColor=white">&nbsp;<img alt="GitHub Actions" src="https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white">&nbsp;<img alt="Python" src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white">&nbsp;<img alt="TFLint" src="https://img.shields.io/badge/TFLint-5C4EE5?style=for-the-badge&logo=terraform&logoColor=white">&nbsp;<img alt="Checkov" src="https://img.shields.io/badge/Checkov-1F2A37?style=for-the-badge">&nbsp;<img alt="Infracost" src="https://img.shields.io/badge/Infracost-FF6B35?style=for-the-badge">&nbsp;<img alt="Gemini" src="https://img.shields.io/badge/Gemini_(optional)-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white">

Para ejecutar el pipeline en tu propio repositorio: [Instalación](docs/es/install.md).

> [!NOTE]
> Los planes, los checks y el comentario del PR ya se ejecutaron en GitHub. El `terraform apply` (manual) todavía no se validó de punta a punta.

<details>
<summary><b>Estructura del repositorio</b></summary>

```text
modules/              Módulos AWS reutilizables (un README cada uno)
infra-example/        Raíces de ejemplo: dev/web-demo y prod/web-demo
tools/reviewer/       El reviewer: ci/ (un archivo por paso del workflow) · lib/ · terraform/ · rules/ · review/ · infracost/ · aws/ · ai/
.github/workflows/    pull-request.yml (checks, planes, comentario) · terraform.yml (plan / apply)
common.yaml           proyecto, state, interruptor de IA, cuenta AWS y raíces desplegables por rama
docs/                 Instalación, arquitectura, mapa de archivos, los checks, estándar de módulos (docs/es/ en español)
.claude/agents/       terraform-ia-engineer: asistente que conoce cómo se construye este repositorio (propone, nunca ejecuta comandos)
```

</details>
