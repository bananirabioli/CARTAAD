# Despliegue en un VPS

Ubuntu Server 24.04 LTS (o Debian 12), mínimo 4 GB de RAM y 2 vCPU. Docker corre todo; el único servicio expuesto es
Caddy, que termina HTTPS y pide usuario y contraseña antes de mostrar la app (todas las cuentas de la semilla usan la
contraseña pública `demo1234`, así que el sitio no debe quedar abierto).

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

Agrega al final de `.env` (las comillas simples son necesarias: el hash contiene `$`):

```bash
DOMAIN=cartaad.tudominio.com
SECRET_KEY=<salida de: openssl rand -hex 32>
BASIC_AUTH_USER=cartaad
BASIC_AUTH_HASH='<salida de: docker run --rm caddy:2-alpine caddy hash-password --plaintext "tu-contraseña">'
# DEMO_MODE=false   # oculta "Ver como" y los botones de acceso rápido; las cuentas demo siguen existiendo
```

`SECRET_KEY` firma las sesiones: si cambia, se cierran todas.

## 3. Levantar

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f caddy   # certificado y errores
```

La primera vez construye las imágenes, migra la base y carga la semilla (varios minutos). Para no repetir los `-f`:
`export COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml`.

## 4. Actualizar y respaldar

```bash
git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db pg_dump -U cartaad cartaad | gzip > cartaad-$(date +%F).sql.gz
```

Además de la base, los archivos generados viven en el volumen `files` (`docker volume inspect cartaad_files`).
