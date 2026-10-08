# infra-example

[English](README.md) · Español

Dos **configuraciones raíz** de ejemplo construidas con `modules/`: `dev/web-demo` y `prod/web-demo`. El reviewer y los workflows las tratan
como cualquier otra raíz; nada de la plataforma depende de estos nombres. La instalación, las ramas, los secrets y el pipeline están en
[docs/es/install.md](../docs/es/install.md) y [docs/es/architecture.md](../docs/es/architecture.md).

Una capa web en una VPC: un Application Load Balancer delante de un Auto Scaling Group de instancias, con Aurora detrás.

```text
infra-example/
├── dev/web-demo/                una raíz, un state
│   ├── main.tf                  lee common.yaml e inputs.yaml en locals; preconditions (claves obligatorias, nombre de carpeta, política de prod)
│   ├── network.tf               VPC y los tres security groups (balanceador, aplicación, base de datos)
│   ├── database.tf              Aurora
│   ├── load_balancer.tf         Application Load Balancer, target group, listener
│   ├── web.tf                   rol de las instancias, launch template, Auto Scaling Group
│   ├── outputs.tf               nombre DNS, endpoints, ARN del secret, resumen
│   ├── inputs.yaml              los valores de este ambiente
│   └── web-user-data.sh.tftpl   script de arranque de las instancias web (servidor web de ejemplo con /health)
└── prod/web-demo/               los mismos archivos (el de cómputo se llama `ec2.tf`), con valores de producción
```

Los archivos `.tf` son los mismos en ambas raíces. Lo que cambia entre ambientes son los datos (`inputs.yaml`), más la política de producción
que aplica `main.tf`.

## Dónde vive cada configuración

| Configuración | Dónde |
| --- | --- |
| Nombre del proyecto, state, interruptor de IA, cuentas | `common.yaml` en la raíz del repositorio |
| Ambiente, owner, centro de costo y todo lo demás del ambiente | `inputs.yaml` (`main.tf` comprueba que `environment` sea igual al nombre de la carpeta padre) |
| Tags obligatorios | `project` de `common.yaml` más `environment`, `owner`, `cost_center` de `inputs.yaml` |
| Región AWS | el secret `AWS_REGION` (no hay bloque provider que copiar) |
| Versión de Terraform | `.terraform-version` en la raíz; se necesita `>= 1.11` por el lock nativo de S3 |
| State remoto | lo genera el pipeline; no hay nada que escribir a mano (ver [arquitectura](../docs/es/architecture.md#state)) |

## inputs.yaml

Solo YAML en estilo de bloques (sin llaves ni listas en línea).

| Clave | Significado |
| --- | --- |
| `environment`, `owner`, `cost_center` | Tags obligatorios; `environment` debe ser `dev`, `staging` o `prod` e igual al nombre de la carpeta |
| `ports` | `app` y `db`: se definen una vez y se usan en los security groups, el target group, la base de datos y las instancias |
| `network` | `cidr_block`, `nat_gateway_mode` opcional (`none` por defecto, `single`, `per_az`), `availability_zones`, un CIDR público y uno privado por zona |
| `security_groups.<alb\|app\|db>` | Reglas `ingress` / `egress`: `description`, `port` (un número o `app`/`db`/`https`/`http`), `protocol` opcional, y una de `cidr_ipv4` (`vpc` = el CIDR de la VPC) o `source_sg`; `alb.allow_public_ingress` permite `0.0.0.0/0` |
| `database` | `engine` (`postgresql` o `mysql`), `engine_version`, `database_name`, `instance_class`, `backup_retention_days`, `deletion_protection`, `skip_final_snapshot`, `instances`, `cluster_parameters`, `serverless_v2` opcional |
| `alb` | `internal`, `deletion_protection`, `target_groups`, `listeners` (`forward`, `redirect` o `fixed_response`), `rules` opcional |
| `instance_role` | `assume_role_services`, `managed_policy_arns`, `create_instance_profile`, `allow_read_db_secret` |
| `compute` | `target_group`, `instance_type`, `ami_id` (null = última AL2023; fíjala en producción), tamaño del volumen, `min/desired/max_size`, health check, instance refresh, `scaling_policies` |

Cambiar `database.engine` a `mysql` también requiere un `engine_version` que coincida (por ejemplo `8.0.mysql_aurora.3.05.2`): el módulo
aurora rechaza una combinación incorrecta.

## Qué se comprueba y quién lo hace

- **`main.tf`**, en cada plan: claves obligatorias, un CIDR de subred por zona, `compute.min_size <= max_size` y la **política de
  producción**: un listener HTTPS, `nat_gateway_mode = per_az`, protección contra borrado de la base de datos con snapshot final, al menos
  dos instancias de base de datos y `compute.min_size >= 2`. Como vive en la raíz, también protege un `apply` hecho desde una laptop, no solo el CI.
- **Las variables tipadas de los módulos:** CIDRs, enumeraciones, tamaños, nombres.
- **El reviewer** ([los checks](../docs/es/checks.md)): el plan (reemplazar una base de datos en una raíz protegida) y el aumento de costo.

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
(`aws rds describe-db-engine-versions --engine aurora-postgresql --query 'DBEngineVersions[].EngineVersion'`), el ARN del certificado de prod
en `alb.listeners` (hoy es un marcador) y un `compute.ami_id` fijo en prod.

| Falla | Efecto | Mitigación |
| --- | --- | --- |
| Caída de una zona | Se pierde la mitad de la capacidad web y de base de datos | Dos zonas; prod: al menos dos instancias web y dos de base de datos, NAT por zona |
| Falla del writer | Failover a un reader | Prod corre dos instancias de base de datos |
| Versión defectuosa del launch template | La renovación gradual se detiene | `min_healthy_percentage`; revisa el plan |

## Agregar un ambiente

Copia `infra-example/dev/web-demo` a `infra-example/<ambiente>/web-demo`, pon `environment` en `inputs.yaml` igual al nombre de la carpeta
padre, edita los valores y agrega la nueva raíz bajo `terraform.deploy` de la rama que deba aplicarla. El bucket y la clave del state salen de
la carpeta y de la cuenta.

---

[← README del repositorio](../README.es.md)
