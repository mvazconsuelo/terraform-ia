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
project: terraform-ia
backend:
  encrypt: true
  use_lockfile: true
ai:
  enabled: false                # true cuando exista GEMINI_API_KEY
terraform:
  environments:                 # cada ambiente, definido una vez: la rama que lo despliega y sus raíces
    dev:
      branch: develop
      roots:
        - infra-example/dev/web-demo
    prod:
      branch: main
      roots:
        - infra-example/prod/web-demo
```

En `terraform:`, `environments` es obligatorio (cada uno necesita su `branch` y `roots`; la cuenta de AWS de cada rama es una variable, ver abajo); el resto es opcional. Ver [arquitectura](architecture.md#configuración).

## 3. Bucket de state (una vez por cuenta y región)

```bash
B=terraform-ia-tfstate-<account id>-<region>
aws s3api create-bucket --bucket $B --region <region>      # fuera de us-east-1 agrega: --create-bucket-configuration LocationConstraint=<region>
aws s3api put-bucket-versioning --bucket $B --versioning-configuration Status=Enabled
aws s3api put-public-access-block --bucket $B --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

## 4. Secrets (a nivel de repositorio)

| Secret | Obligatorio | Uso | Dónde obtenerlo |
| --- | --- | --- | --- |
| `AWS_ACCESS_KEY_ID_DEVELOP`, `AWS_SECRET_ACCESS_KEY_DEVELOP` | sí | `develop` y cualquier otra rama | [Consola IAM de AWS](https://console.aws.amazon.com/iam/home#/users) → el usuario → *Security credentials* → *Create access key*, en la cuenta de **dev** · [guía](https://docs.aws.amazon.com/IAM/latest/UserGuide/access-key-self-managed.html) |
| `AWS_ACCESS_KEY_ID_MAIN`, `AWS_SECRET_ACCESS_KEY_MAIN` | sí | `main` (producción) | La misma consola, en la cuenta de **producción** |
| `AWS_REGION` | sí | Región del provider y del bucket de state | A tu elección, por ejemplo `us-east-1` |
| `INFRACOST_API_KEY` | no | Sección de costos | [Panel de Infracost](https://dashboard.infracost.io) (gratis) · [documentación](https://www.infracost.io/docs/) |
| `GEMINI_API_KEY` | no | Resumen de IA | [Google AI Studio → API keys](https://aistudio.google.com/apikey) |
| `GEMINI_MODEL` | no | Reemplaza el modelo por defecto; déjalo sin definir si no lo necesitas | [Modelos de Gemini](https://ai.google.dev/gemini-api/docs/models) · [límites de uso](https://ai.google.dev/gemini-api/docs/rate-limits) |
| `GEMINI_FALLBACK_MODEL` | no | Un segundo modelo, que se usa solo cuando el principal está saturado (503) o sin cuota (429); las cuotas son por modelo | Las mismas listas de arriba |

Dónde guardarlos: `https://github.com/<owner>/<repo>/settings/secrets/actions` (reemplaza `<owner>/<repo>`) · [documentación de GitHub sobre secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets) · [`gh secret set`](https://cli.github.com/manual/gh_secret_set).

```bash
# Obligatorios: las llaves de cada rama y la región
gh secret set AWS_ACCESS_KEY_ID_DEVELOP
gh secret set AWS_SECRET_ACCESS_KEY_DEVELOP
gh secret set AWS_ACCESS_KEY_ID_MAIN
gh secret set AWS_SECRET_ACCESS_KEY_MAIN
gh secret set AWS_REGION

# Opcionales: la sección de costos y el resumen de IA
gh secret set INFRACOST_API_KEY
gh secret set GEMINI_API_KEY
gh secret set GEMINI_MODEL
gh secret set GEMINI_FALLBACK_MODEL

gh secret list      # solo los nombres, nunca los valores
```

`gh secret set` guarda un secret por comando y te pide el valor, así que no queda en el historial de tu terminal. Nunca subas llaves al repositorio; rota las que se hayan expuesto.


## 5. Variables (a nivel de repositorio)

La cuenta de AWS a la que debe pertenecer cada par de llaves **no está escrita en el repositorio**: es una variable del repositorio (no es un secret, y no es pública: solo la ve quien colabora en el repositorio).
Antes de `init` el pipeline le pregunta a AWS la cuenta de las llaves y se detiene si no es esta.

| Variable | Obligatoria | Uso |
| --- | --- | --- |
| `AWS_ACCOUNT_ID_DEVELOP` | sí | La cuenta de las llaves de `develop` (y de cualquier otra rama) |
| `AWS_ACCOUNT_ID_MAIN` | sí | La cuenta de las llaves de `main` (producción) |

```bash
gh variable set AWS_ACCOUNT_ID_DEVELOP --body "<id de la cuenta de dev>"
gh variable set AWS_ACCOUNT_ID_MAIN --body "<id de la cuenta de producción>"
```
O en `https://github.com/<owner>/<repo>/settings/variables/actions`. Comprobalas con `gh variable list`. Si falta una variable, la ejecución se detiene y dice cuál.

## 6. Abre un PR

Crea una rama desde `develop`, cambia algo pequeño y abre un PR hacia `develop`. Obtienes un check por cada aspecto, un `plan` de solo lectura por cada raíz afectada y un comentario con el veredicto, el plan, el costo y el ambiente al que llega. **Fusionar nunca toca AWS.** Para desplegar, ejecuta `terraform.yml` a mano (abajo); el primer apply crea recursos facturables (Aurora, balanceador de carga).

Ejecución manual (la única forma de desplegar). `--ref` elige la rama, y con ella las llaves y la cuenta AWS. La rama debe estar nombrada por un ambiente en `common.yaml` y la raíz debe pertenecerle; una ejecución desde cualquier otra rama no hace nada.

```bash
gh workflow run terraform.yml --ref develop -f root=infra-example/dev/web-demo -f mode=plan
gh workflow run terraform.yml --ref develop -f root=infra-example/dev/web-demo -f mode=apply
```

Lo mismo desde GitHub: *Actions* → **terraform** en la lista de la izquierda (no en *All workflows*, donde el botón no aparece) → **Run workflow**. Elige la rama en *Use workflow from*, escribe la `root` y elige el `mode`: `plan` es el valor por defecto, `apply` hay que elegirlo. El bucket de state de esa cuenta debe existir antes (paso 3).

Si un PR no muestra ningún check, algún archivo de workflow es inválido: ejecuta `actionlint .github/workflows/*.yml`.

---

[README](../../README.es.md) · [Siguiente: Cómo funciona →](architecture.md)
