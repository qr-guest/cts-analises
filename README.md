# Quality Review

Aplicação Streamlit para análise interna de indicadores de qualidade.

Este repositório deve conter apenas código, configuração não sensível e o
catálogo/modelo de metas. Arquivos com dados reais devem ser carregados pelo
usuário na interface da aplicação e não devem ser versionados.

## Inicialização local

Crie e ative um ambiente virtual:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instale as dependências:

```powershell
python -m pip install -r requirements.txt
```

Crie um arquivo `.env` na raiz do projeto:

```env
APP_PASSWORD_G=sua_senha_geral
APP_PASSWORD_C=sua_senha_consulta
APP_DEBUG=false
```

Inicie a aplicação:

```powershell
python -m streamlit run app.py
```

Alternativa, se o `streamlit` estiver no PATH:

```powershell
streamlit run app.py
```

## Carregamento dos dados

Ao abrir a aplicação, carregue pela interface os arquivos operacionais exigidos:

- `CTS.xlsx`
- `Clientes.xlsx`
- `Conexoes_NOC_RVT.xlsx`
- `Conexoes_RessarceBall.xlsx`

A aba `On-Site | Perdas` não carrega mais CSV local automaticamente. Para usá-la,
gere a exportação atualizada pelo SQL consolidado e faça upload do CSV na própria
aba, em `Fonte de dados`.

O arquivo `excel-metas/Todas-metas-2026.xlsx` é tratado como catálogo/modelo de
metas, não como base operacional.

## Política de dados locais

Não versionar arquivos com dados reais, exportações ou informações pessoais.
O `.gitignore` bloqueia extensões e pastas comuns de dados locais.

Por padrão, o app não procura dados locais para o painel On-Site. Se for
necessário testar fallback local apenas em desenvolvimento, defina no `.env`:

```env
ALLOW_LOCAL_DATA=true
```

Não use `ALLOW_LOCAL_DATA=true` em deploy.

## Validação local

Compile os principais arquivos:

```powershell
python -m py_compile app.py service\onsite.py service\analistas.py service\metas.py
```

Rode os testes:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```
