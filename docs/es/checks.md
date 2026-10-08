# Los checks

[English](../checks.md) · Español

Todas las reglas que aplica el reviewer, en un solo lugar. El catálogo es [`tools/reviewer/rules/rules.yaml`](../../tools/reviewer/rules/rules.yaml): esta tabla lo refleja.

Una regla tiene un **ID** (`FAMILIA-NÚMERO`), una **severidad** y una **función** que la implementa. La función se llama como lo que detecta y su docstring dice qué regla es.

## Las familias

| Familia | Qué cubre |
| --- | --- |
| `MODULE` | Cómo se construyen los módulos y qué no debe construirse fuera de uno. |
| `TAGS` | Todo recurso AWS que admite tags lleva los tags obligatorios. |
| `ROOT` | La estructura de una familia de configuraciones raíz (opcional con `terraform.conventions.layout` en `common.yaml`). |
| `COST` | Decisiones que cuestan más de lo necesario. |
| `PLAN` | Qué le hará Terraform a la infraestructura. |

## Las reglas

| Regla | Severidad | Qué detecta | Lee | Función |
| --- | --- | --- | --- | --- |
| `MODULE-001` | High | Capacidad reutilizable implementada fuera de su módulo | el código | `resource_declared_outside_its_module` |
| `MODULE-002` | Medium | Al módulo le faltan archivos obligatorios del contrato | el código | `module_missing_required_files` |
| `MODULE-003` | Medium | El recurso no sigue la convención de nombre `this` | el código | `resource_has_arbitrary_name` |
| `MODULE-004` | Medium | Una variable usa `type = any` | el código | `variable_typed_any` |
| `MODULE-005` | Medium | Componente de un dominio ubicado fuera de la carpeta de su dominio | el código | `component_outside_domain_folder` |
| `MODULE-006` | High | Auto Scaling Group gestionado directamente para EKS | el código | `eks_autoscaling_group_declared_directly` |
| `TAGS-001` | High | Un recurso con tags no recibe los tags obligatorios | el código | `resource_missing_mandatory_tags` |
| `TAGS-002` | Medium | El módulo no expone el contrato de entrada de los tags obligatorios | el código | `module_missing_tag_variables` |
| `TAGS-003` | High | Un Auto Scaling Group no propaga los tags obligatorios | el código | `autoscaling_group_does_not_propagate_tags` |
| `ROOT-001` | High | La raíz no sigue su estructura *(opcional)* | el código | `root_breaks_layout` |
| `ROOT-002` | High | Los archivos de una raíz difieren de los de sus pares *(opcional)* | el código | `root_files_differ` |
| `COST-001` | Medium | NAT gateway por zona en una configuración no protegida | el código | `nat_gateway_per_zone_in_unprotected_root` |
| `COST-002` | Medium | Infracost reporta un aumento mensual grande | el plan / Infracost | `plan_cost_increase_above_threshold` |
| `PLAN-001` | Critical | El plan destruye o reemplaza un recurso con estado | el plan / Infracost | `plan_destroys_stateful_resource` |

- **Checks sobre el código** (`rules/code_rules.py`) leen los archivos `.tf`. El job `repository contract` los ejecuta sobre todo el repositorio; el comentario lista los hallazgos en archivos y carpetas que el PR toca.
- **Checks sobre el plan** (`rules/plan_rules.py`) leen el plan de Terraform saneado y la estimación de Infracost de cada raíz afectada.

## Cómo una regla se convierte en veredicto

`REQUEST_CHANGES` cuando un hallazgo confirmado es **High** o **Critical**, o cuando falló un check externo (`terraform fmt`, los checks de Python (ruff, mypy), `validate`, TFLint, el contrato del repositorio). Checkov corre con `--soft-fail`: sus hallazgos aparecen como advertencia y todavía no bloquean. Todo lo demás es `PASS`; las severidades menores igual se listan en el comentario. `PLAN-001` es Critical en una raíz protegida y en todas las raíces de un PR hacia producción.

## Agregar una regla

1. Agrega una entrada a `rules.yaml`: `id`, `category`, `severity`, `check`, `title`, `explanation`, `recommendation`, más los parámetros propios del check.
2. Escribe la función en `code_rules.py` (decorada con `@check("<nombre>")`) o en `plan_rules.py` (decorada con `@plan_check("<nombre>")`), con un nombre que diga lo que detecta.
3. Agrega su fila a la tabla de arriba, y a la tabla de [estándar de módulos](module-standard.md) si hace cumplir el estándar.
4. Si el nombre de `check:` no tiene función, el reviewer se detiene con un error: una regla nunca se omite en silencio.

## Qué no es una regla a propósito

`terraform fmt` y `validate`, TFLint y Checkov son la autoridad en formato, sintaxis, lint y seguridad genérica, e Infracost en precios. Las reglas de arriba son solo lo que esas herramientas no pueden saber: límites de módulos, nombres, tags obligatorios, estructura de raíces y la correlación del plan y el costo con los estándares de este repositorio.

---

[← Anterior: Qué es cada archivo](files.md) · [README](../../README.es.md) · [Siguiente: Estándar de módulos →](module-standard.md)
