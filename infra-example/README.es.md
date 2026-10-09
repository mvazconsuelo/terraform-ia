# infra-example

[English](README.md) · Español

Dos **configuraciones raíz** de ejemplo construidas con `modules/`: `dev/web-demo` y `prod/web-demo`. El reviewer y los workflows las tratan
como cualquier otra raíz; nada de la plataforma depende de estos nombres. La instalación, las ramas, los secrets y el pipeline están en
[docs/es/install.md](../docs/es/install.md) y [docs/es/architecture.md](../docs/es/architecture.md).

`inputs.yaml` pertenece al proyecto que construye la infraestructura, que aquí es este ejemplo: los módulos no saben nada de él. Sus
variables son su contrato, y los `.tf` de la raíz traducen `inputs.yaml` a ellas.

Una capa web en una VPC: un Application Load Balancer delante de un Auto Scaling Group de instancias, con Aurora detrás.

```text
infra-example/
├── dev/web-demo/                una raíz, un state
│   ├── main.tf                  lee inputs.yaml y common.yaml (inputs, tags)
│   ├── network.tf               VPC y los tres security groups (balanceador, aplicación, base de datos)
│   ├── database.tf              Aurora
│   ├── load_balancer.tf         Certificado ACM, Application Load Balancer, target group, listener
│   ├── ec2.tf                   rol de las instancias, launch template, Auto Scaling Group
│   ├── data.tf                  data sources (la política IAM con la que las instancias leen el secreto de la base)
│   ├── outputs.tf               nombre DNS, endpoints, ARN del secret, resumen
│   ├── inputs.yaml              los valores de este ambiente
│   └── web-user-data.sh.tftpl   script de arranque de las instancias web (servidor web de ejemplo con /health)
└── prod/web-demo/               los mismos archivos, con valores de producción
```

Los archivos `.tf` son los mismos en ambas raíces. Lo que cambia entre ambientes son los datos (`inputs.yaml`), más la política de producción
que aplica el reviewer (`POLICY-001`).

## Dónde vive cada configuración

| Configuración | Dónde |
| --- | --- |
| Nombre del proyecto, state, interruptor de IA | `common.yaml` en la raíz del repositorio |
| Owner, centro de costo y todo lo demás del ambiente | `inputs.yaml` |
| Nombres de los componentes | un `name` en cada bloque de `inputs.yaml`, con el nombre físico completo (`terraform-ia-dev-db`); el `.tf` solo lo lee |
| Tags obligatorios | `owner` y `cost_center` en el bloque `tags:` del `inputs.yaml` de cada raíz (cada proyecto pone los suyos), más el `project` y el `environment` de `common.yaml`; `main.tf` los une en `local.tags` y cada llamada a un módulo pasa `tags = local.tags` |
| Región AWS | el secret `AWS_REGION` (no hay bloque provider que copiar) |
| Versión de Terraform | `.terraform-version` en la raíz; se necesita `>= 1.11` por el lock nativo de S3 |
| State remoto | lo genera el pipeline; no hay nada que escribir a mano (ver [arquitectura](../docs/es/architecture.md#state)) |

## inputs.yaml

Solo YAML en estilo de bloques (sin llaves ni listas en línea).

| Clave | Significado |
| --- | --- |
| `tags` | `owner` y `cost_center`. El `project` y el `environment` no se ponen aquí: vienen de `common.yaml` |
| `network` | `name`, `cidr_block`, `nat_gateway_mode` opcional (`none` por defecto, `single`, `per_az`), `availability_zones`, un CIDR público y uno privado por zona |
| `security_groups.<alb\|app\|db>` | `name`, Reglas `ingress` / `egress`: `description`, `port` (un número), `protocol` opcional, y una de `cidr_ipv4` (`vpc` = el CIDR de la VPC) o `source_sg`; `alb.allow_public_ingress` permite `0.0.0.0/0` |
| `database` | `name`, `port`, `engine` (`postgresql` o `mysql`), `engine_version`, `database_name`, `instance_class`, `backup_retention_days`, `deletion_protection`, `skip_final_snapshot`, `instances`, `cluster_parameters`, `serverless_v2` opcional |
| `certificate` | `name`, `domain_name`, `subject_alternative_names`, `zone_id` (la zona de Route 53 del dominio; vacío no crea registros de validación) |
| `alb` | `name`, `internal`, `deletion_protection`, `target_groups`, `listeners` (cada uno con su `port`; la acción es `forward`, `redirect` o `fixed_response`), `rules` opcional |
| `instance_role` | `name`, `assume_role_services`, `managed_policy_arns`, `create_instance_profile`, `allow_read_db_secret` |
| `compute` | `name`, `port` (el que sirven las instancias), `target_group`, `instance_type`, `ami_id` (null = última AL2023; fíjala en producción), tamaño del volumen, `min/desired/max_size`, health check, instance refresh, `scaling_policies` |

Cambiar `database.engine` a `mysql` también requiere un `engine_version` que coincida (por ejemplo `8.0.mysql_aurora.3.05.2`): el módulo
aurora rechaza una combinación incorrecta.

## Qué se comprueba y quién lo hace

- **Las variables tipadas de los módulos:** CIDRs, enumeraciones, tamaños, nombres, la cantidad de subredes por zona, los tamaños del Auto
  Scaling Group y el formato de `tags.environment`. Cada módulo comprueba sus propias entradas, así que lo hace donde sea que se use.
- **El reviewer** ([los checks](../docs/es/checks.md)), en cada pull request y antes de planificar nada:
  - `ROOT-001` y `ROOT-002`: la raíz tiene solo sus archivos listados, y son idénticos en `dev` y `prod`.
  - `ROOT-003` y `ROOT-004`: la raíz figura bajo un ambiente de `terraform.environments`, y su bloque `tags` tiene `owner` y `cost_center` y no
    define el `project` ni el `environment`.
  - `POLICY-001`: una raíz cuyo ambiente es de producción tiene un listener HTTPS, protección contra borrado de la base de datos con
    snapshot final, `nat_gateway_mode = per_az`, al menos dos instancias de base de datos y `compute.min_size >= 2`. Los requisitos son
    datos en `rules.yaml`, así que otro proyecto los cambia ahí.
  - El plan (reemplazar una base de datos en una raíz protegida) y el aumento de costo.

## Notas de diseño

- **El tráfico se separa por capas con security groups.** El grupo de la aplicación solo acepta tráfico del balanceador, y el de la base de
  datos solo el de la aplicación. Las direcciones inversas usan el CIDR de la VPC con puertos explícitos, porque referenciarse en ambos sentidos
  sería una dependencia circular.
- **El egress es explícito.** Ninguna capa tiene egress abierto. Con el `nat_gateway_mode: none` por defecto la capa de aplicación no tiene
  internet: usa `single` para que las instancias puedan instalar paquetes, o agrega VPC endpoints (no están en este ejemplo).
- **Los secretos no aparecen en outputs ni en user data.** Aurora genera la contraseña en Secrets Manager; las instancias solo reciben el
  ARN del secret y una política IAM para leerlo.
- **El state es uno por ambiente.** Cualquier cambio planifica y bloquea todo el ambiente, base de datos incluida.

## Antes del primer apply

El primer apply crea recursos facturables: NAT gateway (uno en dev cuando se habilita, uno por zona en prod), balanceador de carga, Aurora y EC2.
Dev está dimensionado para ser barato pero no es gratis: destrúyelo cuando no lo uses. Define un `database.engine_version` real en `inputs.yaml`
(`aws rds describe-db-engine-versions --engine aurora-postgresql --query 'DBEngineVersions[].EngineVersion'`), el dominio y la zona de `certificate`
(hoy `example.com`, un ejemplo) y un `compute.ami_id` fijo en prod.

| Falla | Efecto | Mitigación |
| --- | --- | --- |
| Caída de una zona | Se pierde la mitad de la capacidad web y de base de datos | Dos zonas; prod: al menos dos instancias web y dos de base de datos, NAT por zona |
| Falla del writer | Failover a un reader | Prod corre dos instancias de base de datos |
| Versión defectuosa del launch template | La renovación gradual se detiene | `min_healthy_percentage`; revisa el plan |

## Agregar un ambiente

Copia `infra-example/dev/web-demo` a `infra-example/<ambiente>/web-demo`, edita los valores y agrega el ambiente nuevo bajo `terraform.environments` en `common.yaml`, con su `branch` y sus `roots`. El bucket y la clave del state salen de
la carpeta y de la cuenta de su rama (una variable del repositorio, ver [Instalación](../docs/es/install.md)).

---

[← README del repositorio](../README.es.md)
