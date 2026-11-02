# Despliegue en un VPS

Ubuntu Server 24.04 LTS (o Debian 12), mínimo 4 GB de RAM y 2 vCPU. Docker corre todo; el único servicio expuesto es
Caddy, que termina HTTPS. El acceso es el inicio de sesión de la app con el usuario maestro (`ADMIN_EMAIL` /
`ADMIN_PASSWORD`); no hay cuentas demo con contraseña pública.

## 1. Servidor

Un dominio con registro A (y AAAA si hay IPv6) hacia la IP del VPS; sin él Caddy no puede emitir el certificado.

```bash
curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER   # vuelve a entrar a la sesión
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443 && sudo ufw enable
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 2. Código y configuración

```bash
git clone <url-del-repo> cartaad && cd cartaad
cp .env.example .env
```

Define en `.env`:

```bash
DOMAIN=cartaad.tudominio.com
SECRET_KEY=<salida de: openssl rand -hex 32>
ADMIN_EMAIL=tu@correo.mx
ADMIN_PASSWORD=<salida de: openssl rand -base64 18>
OPENROUTER_API_KEY=sk-or-...
```

`SECRET_KEY` firma las sesiones: si cambia, se cierran todas. `ADMIN_*` solo se usan al primer arranque con la base
vacía; después la contraseña vive en la base. La llave de OpenRouter se puede agregar o cambiar en cualquier momento:
basta con `docker compose ... up -d api worker beat` para que la tomen.

Para la demo offline con datos ficticios: `DEMO_MODE=true`, `LLM_PROVIDER=mock`, `IMAGE_PROVIDER=placeholder` y
`VIDEO_PROVIDER=none`.

## 3. Levantar

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f caddy   # certificado y errores
```

La primera vez construye las imágenes, migra la base y crea el cliente inicial, el usuario maestro y su cuenta
principal (varios minutos). Para no repetir los `-f`:
`export COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml`.

## 4. Actualizar y respaldar

```bash
git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db pg_dump -U cartaad cartaad | gzip > cartaad-$(date +%F).sql.gz
```

Además de la base, los archivos generados viven en el volumen `files` (`docker volume inspect cartaad_files`).

## 5. Volver a empezar con la base vacía

Borra solo la base y los archivos; **no** uses `down -v`, que también borraría los certificados de Caddy:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml stop api worker beat web db
docker compose -f docker-compose.yml -f docker-compose.prod.yml rm -f api worker beat web db
docker volume rm cartaad_pgdata cartaad_files
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```
