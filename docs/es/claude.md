# Trabajar con Claude Code

[English](../claude.md) · Español

El repositorio está preparado para [Claude Code](https://code.claude.com/docs): conoce las convenciones, tiene un agente ingeniero, tres skills y dos redes de seguridad.
No lo necesitás para usar el proyecto; es para quien lo mantiene.

## Qué hay en el repositorio

| Archivo | Qué hace |
| --- | --- |
| [`CLAUDE.md`](../../CLAUDE.md) | Claude lo lee en cada sesión: cómo funciona el repositorio y todas las convenciones. |
| `.claude/agents/terraform-ia-engineer.md` | El ingeniero: propone primero, edita solo cuando aprobás y nunca ejecuta comandos. |
| `.claude/skills/new-module`, `new-rule`, `new-root` | Las listas paso a paso que Claude sigue cuando pedís un módulo, una regla o un ambiente. |
| `.claude/settings.json`, `.claude/hooks/after_edit.py` | Después de cada edición: `ruff` y `mypy` en Python, `terraform fmt` en `.tf`. Bloquea los comandos que son tuyos: escrituras de git, los `gh` que publican, `terraform apply`. |

## Instalar

1. Instalá Claude Code: [documentación](https://code.claude.com/docs).
2. Abrí una terminal en la raíz del repositorio y ejecutá `claude`. La primera vez te pide confiar en el hook y los ajustes del proyecto: aceptá.

## Usarlo

**Una sesión normal**: ejecutá `claude` y pedí. Las skills arrancan solas cuando el pedido coincide (*"creá un módulo para SQS"*, *"agregá una regla que..."*, *"agregá un ambiente staging"*).

**El agente ingeniero**: para un cambio con varias partes, donde querés una propuesta antes de que se edite nada.

```bash
claude --agent terraform-ia-engineer
```

O, dentro de una sesión, `@agent-terraform-ia-engineer ...`, o *"usá el agente terraform-ia-engineer para ..."*. Un alias ahorra tipeo: `alias tia='claude --agent terraform-ia-engineer'`.

| Querés | Usá |
| --- | --- |
| Un módulo, una regla o un ambiente, con una propuesta primero | El agente |
| Un cambio chico, correr los checks, revisar un pull request | Una sesión normal |

## El flujo con el agente

1. Pedís. Por ejemplo: *"Quiero un módulo `sqs` con una cola de mensajes muertos. Proponé primero."*
2. Responde con lo que entendió, lo que todavía necesita saber y una propuesta (archivos y docs). **Todavía no cambia nada.**
3. Aprobás en tu siguiente mensaje (*"aprobado, hacelo"*).
4. Edita. El hook da formato y revisa cada archivo.
5. Te da los comandos que tenés que correr: la verificación y los de git. No tiene terminal.

Todo módulo o regla que crea trae su test y la documentación en inglés y español. El pipeline ejecuta los tests.

## Lo que Claude nunca hace

No hace commit, push, merge ni abre pull requests; no despliega ni toca AWS; no escribe llaves ni ids de cuenta. Esos comandos están bloqueados en `.claude/settings.json`.
Git y todo despliegue son tuyos: [Cómo funciona](architecture.md).

---

[← Anterior: Los checks](checks.md) · [README](../../README.es.md)
