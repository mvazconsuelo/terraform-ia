# Política de seguridad

[English](../../SECURITY.md) · Español

## Cómo reportar una vulnerabilidad

**No abras un issue público.** Usá el reporte privado de GitHub: la pestaña **Security** del repositorio → **Report a vulnerability**. Vas a recibir una respuesta
en pocos días.

Qué se considera una vulnerabilidad acá:

- El reviewer o un workflow filtra un secreto o una llave (el comentario del PR, los logs, el resumen de IA).
- Una forma de hacer que un workflow ejecute algo que no debería (inyección de scripts por el título de un PR, el nombre de una rama o una entrada), o de desplegar en AWS sin la ejecución manual.
- Un módulo con valores por defecto inseguros (público por defecto, sin cifrar, abierto a internet).

También se agradece una debilidad en una dependencia o en una GitHub Action: Dependabot cubre las ya conocidas.

## Qué está protegido

- Fusionar un pull request nunca toca AWS. Desplegar es una ejecución manual de `terraform.yml`, y solo desde la rama de un ambiente.
- La IA nunca recibe el contenido de los archivos, y todo texto que pueda llevar un secreto se redacta antes de salir del repositorio.
- Los pull requests de forks no reciben secrets.

## Si usás este repositorio

Nunca subas llaves. Si una llave se expuso, rotala primero y limpiá después. Las llaves de AWS viven en los secrets del repositorio, un par por rama.
