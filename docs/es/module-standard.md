# Estándar de módulos

[English](../module-standard.md) · Español

El contrato que sigue cada módulo de `modules/`. Los IDs de regla se refieren a [`tools/rules/rules.yaml`](../../tools/rules/rules.yaml).

**Alcance y límites**
- Un módulo es una **capacidad reutilizable** (VPC, Lambda, S3, Aurora, ALB, IAM, ...), utilizable de forma independiente y nunca atada a
  un ambiente. Una capacidad DEBE vivir en su módulo; las configuraciones raíz consumen módulos y NO DEBEN declarar los recursos
  subyacentes (`MODULE-001`).
- Los dominios con varios componentes viven bajo `modules/<dominio>/<componente>`: `eks` (cluster, node-group, addons), `ec2`
  (launch-template, instances, asg), `elb` (nlb, alb) y `route53` (zone, records). Los balanceadores de carga no forman parte del dominio EC2. Están prohibidos los
  `modules/eks-*`, `ec2-*`, `elb-*`, `route53-*`, `nlb` o `alb` de primer nivel (`MODULE-005`).
- `ec2/instances` y `ec2/asg` consumen `ec2/launch-template`; la definición endurecida de la instancia (IMDSv2, cifrado, tags)
  vive solo allí. La capacidad de EKS se expresa con `eks/node-group`, nunca con un Auto Scaling Group directo (`MODULE-006`).
- Los módulos no configuran providers y no llaman a módulos de otro dominio; la conexión entre capacidades se hace en la configuración
  raíz.

**El módulo es la fuente de verdad de cómo se lo llama.** Sus variables (`variables.tf`) y su README son su contrato. Nada de lo que haga un
proyecto lo cambia: los proyectos que llaman a un módulo guardan sus propios valores, en su propio `inputs.yaml`, y los pasan a las variables del módulo tal cual. Una llamada no lleva lógica (ni `for`, ni `try`, ni condiciones que reformen los valores): lo que haya que resolver o dar por omitido es trabajo del módulo.

**Estructura** (`MODULE-002`): son obligatorios `versions.tf`, `variables.tf`, `outputs.tf` y `README.md`; `main.tf`, `locals.tf` y
`data.tf` según haga falta.

**API pública**
- Las entradas expresan *intención*, no detalles del provider (`groups = { system = {...} }`). Toda variable tiene `type` y
  `description`; `type = any` está prohibido (`MODULE-004`); usa `object`, `map(object)` y `optional()`.
- Agrega `validation` para CIDRs, enumeraciones, rangos de tamaño, nombres y opciones mutuamente excluyentes; las invariantes entre
  variables usan `lifecycle.precondition`. Los valores por defecto son seguros y baratos (sin NAT, privado, cifrado, con versionado).
- Los outputs tienen `description`, exponen los IDs y ARNs que necesitan los consumidores y nunca secretos. Los cambios incompatibles
  requieren una versión mayor y una nota de migración.
- TFLint hace cumplir las variables y outputs documentados y los rangos acotados de `required_version` y de providers.

**Tags obligatorios** (`TAGS-001`, `TAGS-002`, `TAGS-003`): todo recurso que admite tags recibe `Name`, `Environment`, `Owner`,
`CostCenter`, `Project` y `ManagedBy` (literal `"terraform"`). Los módulos reciben un objeto `tags` (`environment`, `owner`,
`cost_center`, `project`) y un mapa libre `extra_tags`; `locals.tags = merge(var.extra_tags, local.mandatory_tags)` para que los tags
obligatorios siempre ganen. Los Auto Scaling Groups usan bloques `tag` con `propagate_at_launch`. Los `default_tags` del provider no
lo reemplazan.

**Nombres** (`MODULE-003`): el recurso principal de un tipo es `this`; los adicionales usan nombres de rol (`public`, `private`); las
variables, outputs y locals van en snake_case sin prefijo de tipo; están prohibidos los nombres arbitrarios (`prod_bucket`, `my_bucket`,
`bucket123`). Los nombres físicos son `<proyecto>-<ambiente>-<componente>[-<calificador>]`, construidos en `locals`; los recursos por
zona agregan la zona; todo recurso con tags tiene un tag `Name` igual a su nombre físico. Las claves de tags van en PascalCase.

**Estilo Terraform**: Terraform `>= 1.11` (lock estable de S3); `for_each` en lugar de `count` (las claves son identificadores
estables, nunca índices de lista), `count` solo para interruptores 0/1; bloques `dynamic` solo para bloques anidados realmente
opcionales o repetidos; sin cuentas, regiones ni zonas fijas en el código; nunca secretos en el código (`sensitive = true`); bloques
`moved` para cada renombre; `depends_on` como último recurso y comentado; sin `local-exec` ni `null_resource` salvo que sea inevitable.

**Ciclo de vida**: los recursos con estado exponen una estrategia de protección (protección contra borrado, `force_destroy = false`);
cada `ignore_changes` lleva un comentario con el sistema dueño del atributo; el README documenta qué entradas fuerzan un reemplazo.

**Documentación**: el README de cada módulo es corto y tiene estas secciones, en este orden. El modelo a copiar es
[`modules/api-gateway/README.md`](../../modules/api-gateway/README.md).
- *Título y propósito*: una línea de qué construye y una línea de **no-objetivos**.
- *Usage*: cómo escribirlo en un proyecto. Primero el bloque de `inputs.yaml` (YAML de bloques; las claves son los nombres de las variables del módulo) y luego la llamada `module` que lo lee con `local.inputs.*`. Lo que viene de otros módulos se cablea en el `.tf`. `tags` es el bloque compartido del proyecto. El módulo sigue siendo la fuente de verdad: el YAML solo muestra cómo darle los valores que piden sus variables.
- *Resources and tags*: los recursos que crea, cuáles admiten tags y los llevan, y los tags obligatorios.
- *Inputs*: los nombres que importan, agrupados, con una referencia a `variables.tf` para tipos, valores por defecto y validaciones. Sin tablas generadas.
- *Outputs*: los nombres.
- *Lifecycle*: qué fuerza un reemplazo, qué tiene estado y qué está protegido.
- *Cost*: qué hace subir la factura.

Además, cada módulo figura, con un enlace a su README, en la tabla *Módulos* del [README](../../README.es.md) principal.

**Mantenibilidad**: una responsabilidad por módulo (sepáralo cuando se mezclan dos ciclos de vida); sin lógica copiada entre módulos;
depreca antes de eliminar.

## Cómo se hace cumplir el estándar

El estándar de arriba es el contrato en palabras. Estas son las partes que el reviewer comprueba con código: cada fila es una regla del
[catálogo](checks.md), implementada por una función de [`rules/code_rules.py`](../../tools/rules/code_rules.py).

| El estándar dice | Regla | Función |
| --- | --- | --- |
| Una capacidad vive en su módulo; las raíces no la declaran | `MODULE-001` | `resource_declared_outside_its_module` |
| Un módulo tiene `versions.tf`, `variables.tf`, `outputs.tf` y `README.md` | `MODULE-002` | `module_missing_required_files` |
| El recurso principal es `this`; sin nombres arbitrarios | `MODULE-003` | `resource_has_arbitrary_name` |
| Sin `type = any` | `MODULE-004` | `variable_typed_any` |
| Los componentes viven bajo la carpeta de su dominio (`eks/`, `ec2/`, `elb/`, `route53/`) | `MODULE-005` | `component_outside_domain_folder` |
| La capacidad de EKS sale de `eks/node-group`, nunca de un Auto Scaling Group directo | `MODULE-006` | `eks_autoscaling_group_declared_directly` |
| Todo recurso con tags lleva los tags obligatorios | `TAGS-001` | `resource_missing_mandatory_tags` |
| Un módulo expone las variables `tags` y `extra_tags` | `TAGS-002` | `module_missing_tag_variables` |
| Un Auto Scaling Group propaga los tags a sus instancias | `TAGS-003` | `autoscaling_group_does_not_propagate_tags` |

El resto del estándar (variables y outputs documentados, versiones acotadas de providers, formato) lo comprueban TFLint y
`terraform fmt`/`validate`, que son la autoridad en esos puntos; las pautas de estilo (`for_each` en lugar de `count`, bloques `moved`,
comentarios en `ignore_changes`) son para el revisor humano.

---

[← Anterior: Los checks](checks.md) · [README](../../README.es.md)
