# Instalación

[English](../install.md) · Español

## Requisitos

Un repositorio de GitHub, una o dos cuentas AWS, Terraform ≥ 1.11 (lock nativo de S3 para el state, sin DynamoDB; el repositorio se desarrolla con 1.16), el AWS CLI, `gh` y Python 3.12 con PyYAML.

## 1. Ramas

`main` es producción (déjala como rama por defecto) y `develop` es no productiva.

```bash
git switch -c develop && git push -u origin develop
```

Protege `main` (pull request obligatorio y status checks requeridos): fusionar nunca toca AWS (desplegar es una ejecución manual), pero esa protección es la puerta de los cambios en `main`.

## 2. `common.yaml`

```yaml
project: shop
backend:
  encrypt: true
  use_lockfile: true
ai:
  enabled: false                # true cuando exista GEMINI_API_KEY
terraform:
  accounts:                     # id de la cuenta AWS de las llaves de cada rama; el pipeline se detiene si no coincide
    develop: "111111111111"
    main: "222222222222"
  deploy:                       # raíces que cada rama puede planificar, revisar y desplegar (globs)
    develop:
      - infra-example/dev/*
    main:
      - infra-example/prod/*
```

Todo lo que está bajo `terraform:` salvo `accounts` es opcional. Ver [arquitectura](architecture.md#configuración).

## 3. Bucket de state (una vez por cuenta y región)

```bash
B=shop-tfstate-<account id>-<region>
aws s3api create-bucket --bucket $B --region <region>      # fuera de us-east-1 agrega: --create-bucket-configuration LocationConstraint=<region>
aws s3api put-bucket-versioning --bucket $B --versioning-configuration Status=Enabled
aws s3api put-public-access-block --bucket $B --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

## 4. Secrets (a nivel de repositorio)

| Secret | Obligatorio | Uso |
| --- | --- | --- |
| `AWS_ACCESS_KEY_ID_DEVELOP`, `AWS_SECRET_ACCESS_KEY_DEVELOP` | sí | `develop` y cualquier otra rama |
| `AWS_ACCESS_KEY_ID_MAIN`, `AWS_SECRET_ACCESS_KEY_MAIN` | sí | `main` (producción) |
| `AWS_REGION` | sí | Región del provider y del bucket de state |
| `INFRACOST_API_KEY` | no | Sección de costos (`infracost auth login` da una llave gratuita) |
| `GEMINI_API_KEY` | no | Resumen de IA (Google AI Studio) |
| `GEMINI_MODEL` | no | Reemplaza el modelo por defecto; déjalo sin definir si no lo necesitas |
| `GEMINI_FALLBACK_MODEL` | no | Un segundo modelo, que se usa solo cuando el principal está saturado (503) o sin cuota (429); las cuotas son por modelo |

```bash
gh secret set AWS_ACCESS_KEY_ID_DEVELOP
```

Nunca subas llaves al repositorio; rota las que se hayan expuesto.


## 5. Abre un PR

Crea una rama desde `develop`, cambia algo pequeño y abre un PR hacia `develop`. Obtienes un check por cada aspecto, un `plan` de solo lectura por cada raíz afectada y un comentario con el veredicto, el plan, el costo y el ambiente al que llega. **Fusionar nunca toca AWS.** Para desplegar, ejecuta `terraform.yml` a mano (abajo); el primer apply crea recursos facturables (Aurora, balanceador de carga).

Ejecución manual (la única forma de desplegar). `--ref` elige la rama, y con ella la cuenta AWS; la raíz debe ser una de las que `terraform.deploy` lista para esa rama:

```bash
gh workflow run terraform.yml --ref develop -f root=infra-example/dev/web-demo -f mode=plan
gh workflow run terraform.yml --ref develop -f root=infra-example/dev/web-demo -f mode=apply
```

Si un PR no muestra ningún check, algún archivo de workflow es inválido: ejecuta `actionlint .github/workflows/*.yml`.

---

[README](../../README.es.md) · [Siguiente: Cómo funciona →](architecture.md)
