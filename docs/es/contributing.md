# Contribuir

[English](../../CONTRIBUTING.md) · Español

Gracias por ayudar. Un cambio es bienvenido cuando sigue las convenciones del proyecto, que son pocas y están escritas en [`CLAUDE.md`](../../CLAUDE.md).

## Cómo viaja un cambio

1. Hacé un fork y creá una rama desde `develop` (no producción). `main` es producción.
2. Abrí un pull request hacia `develop`. El pipeline ejecuta `terraform fmt`, `validate`, TFLint, Checkov, `ruff`, `mypy`, los **tests**, el contrato del repositorio, un plan de solo lectura de las raíces que tu cambio afecta, y comenta el resultado.
3. Un hallazgo High o Critical confirmado, o cualquier check fallido, hace que el veredicto sea `REQUEST_CHANGES`.
4. Fusionar no despliega nada: solo el dueño despliega, a mano. Los pull requests de forks no reciben llaves de AWS, así que no tienen plan.

## Qué trae todo cambio

| Si cambiás | También debe tener |
| --- | --- |
| Un módulo (`modules/`) | Su README con el formato estándar, su test en `tests/terraform/` (un archivo por módulo) y su entrada en las tablas de módulos de los README y de `docs/files.md` |
| Una regla del reviewer (`tools/rules/`) | La entrada en `rules.yaml`, la función, un test en `tests/reviewer/` que la rompa a propósito y su fila en `docs/checks.md` |
| Valores de infraestructura (`inputs.yaml`) | Nada escrito a mano en los `.tf`: los `.tf` son iguales en todos los ambientes |
| Cualquier documentación | El archivo en inglés y su copia en español (`docs/es/`, `README.es.md`) |

- Una llamada a un módulo en una raíz pasa los valores tal cual: sin `for`, `try`, `merge` ni condiciones. Si necesitás lógica, va en el módulo (regla `ROOT-005`).
- Los tests los ejecuta el pipeline, no se corren a mano. Viven solo en `tests/`.
- Nunca subas una llave, un token ni un archivo de state.

## Por dónde empezar

[`docs/es/module-standard.md`](module-standard.md) es el contrato de un módulo, [`docs/es/checks.md`](checks.md) lista todas las reglas y [`docs/es/files.md`](files.md)
dice qué es cada archivo. Si usás Claude Code, el repositorio ya trae el agente y las skills `new-module`, `new-rule` y `new-root` que siguen todo esto.
