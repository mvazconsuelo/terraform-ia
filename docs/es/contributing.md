# Contribuir

[English](../../CONTRIBUTING.md) · Español

Este es un proyecto personal. **Cualquiera puede abrir un issue; los pull requests los abre y los fusiona el mantenedor.** El repositorio no acepta pull requests de otras personas.

## Ideas y errores: abrí un issue

Usá el formulario que corresponda: **Bug** (algo no funciona como dice la documentación) o **Improvement** (un módulo, una regla o un cambio que te gustaría).
Para un problema de seguridad no abras un issue: mirá [`SECURITY.md`](security.md).

## Cómo viaja un cambio (el mantenedor)

1. Crear una rama desde `develop` (no producción). `main` es producción.
2. Abrir un pull request hacia `develop`. El pipeline ejecuta `terraform fmt`, `validate`, TFLint, Checkov, `ruff`, `mypy`, los **tests**, el contrato del repositorio, un plan de solo lectura de las raíces que el cambio afecta, y comenta el resultado.
3. Un hallazgo High o Critical confirmado, o cualquier check fallido, hace que el veredicto sea `REQUEST_CHANGES`.
4. Fusionar no despliega nada: solo el mantenedor despliega, a mano. Producción llega a `main` con un pull request de `develop`.

## Qué trae todo cambio

| Si cambiás | También debe tener |
| --- | --- |
| Un módulo (`modules/`) | Su README con el formato estándar, su test en `tests/terraform/` (un archivo por módulo) y su entrada en las tablas de módulos de los README y de `docs/files.md` |
| Una regla del reviewer (`tools/rules/`) | La entrada en `rules.yaml`, la función, un test en `tests/reviewer/` que la rompa a propósito y su fila en `docs/checks.md` |
| Valores de infraestructura (`inputs.yaml`) | Nada escrito a mano en los `.tf`: los `.tf` son iguales en todos los ambientes |
| Cualquier documentación | El archivo en inglés y su copia en español (`docs/es/`, `README.es.md`) |

- Una llamada a un módulo en una raíz pasa los valores tal cual: sin `for`, `try`, `merge` ni condiciones. Si necesitás lógica, va en el módulo (regla `ROOT-005`).
- Los tests los ejecuta el pipeline, no se corren a mano. Viven solo en `tests/`.
- Nunca subas una llave, un token, un id de cuenta ni un archivo de state.

## Por dónde empezar

Las convenciones están en [`CLAUDE.md`](../../CLAUDE.md). [`docs/es/module-standard.md`](module-standard.md) es el contrato de un módulo, [`docs/es/checks.md`](checks.md) lista todas las reglas y
[`docs/es/files.md`](files.md) dice qué es cada archivo. El repositorio trae un agente y las skills `new-module`, `new-rule` y `new-root` para Claude Code que siguen todo esto: ver [`docs/es/claude.md`](claude.md).
