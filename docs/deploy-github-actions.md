# Deploy automatico com GitHub Actions

O workflow `.github/workflows/deploy.yml` roda sempre que houver `git push` na branch `main`.
Ele acessa o servidor via SSH, atualiza o codigo, instala dependencias, cria tabelas que ainda nao existirem e reinicia o servico da aplicacao.

## Secrets necessarios no GitHub

Cadastre em `Settings > Secrets and variables > Actions > Repository secrets`:

- `DEPLOY_HOST`: IP ou dominio do servidor.
- `DEPLOY_USER`: usuario SSH usado no deploy.
- `DEPLOY_PORT`: porta SSH. Opcional, usa `22` se nao for configurada.
- `DEPLOY_SSH_KEY`: chave privada SSH autorizada no servidor.
- `DEPLOY_PATH`: pasta do projeto no servidor. Exemplo: `/var/www/sistema.adv`.
- `DEPLOY_SERVICE`: nome do servico systemd. Exemplo: `sistema-adv`.

## Requisitos no servidor

O servidor precisa ter:

- Python 3 e `python3-venv`.
- Git instalado.
- O repositorio ja clonado em `DEPLOY_PATH`.
- Um virtualenv `venv` ou `.venv`, ou permissao para criar `venv`.
- Um servico systemd para rodar a aplicacao.

Exemplo de preparacao:

```bash
sudo mkdir -p /var/www/sistema.adv
sudo chown -R deploy:deploy /var/www/sistema.adv

cd /var/www/sistema.adv
git clone https://github.com/Anderson0100/Sistema-Juridico-Flask.git .

python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
```

## Permissao para reiniciar o servico

O usuario de deploy precisa conseguir rodar:

```bash
sudo systemctl restart sistema-adv
sudo systemctl --no-pager --full status sistema-adv
```

Para liberar sem senha, crie um arquivo com `sudo visudo -f /etc/sudoers.d/sistema-adv-deploy`:

```bash
deploy ALL=(root) NOPASSWD: /bin/systemctl restart sistema-adv, /bin/systemctl --no-pager --full status sistema-adv
```

Troque `deploy` e `sistema-adv` pelos nomes reais do seu servidor.

## Observacoes

- O arquivo `.env` deve ficar somente no servidor, dentro de `DEPLOY_PATH`, e nao deve ser commitado.
- O workflow usa `ENABLE_SCHEDULER=false` apenas ao rodar `db.create_all()` durante o deploy, para nao iniciar o agendador nesse passo.
- O deploy faz `git reset --hard origin/main` no servidor. Alteracoes manuais feitas dentro de `DEPLOY_PATH` serao descartadas.
