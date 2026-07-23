# Pi Operations — Lucho

Procedimiento estándar para que el agente Pi (ejecutándose en el VPS) actualice
el código fuente de Lucho y reinicie la aplicación de forma segura y determinista.

**Ejecutar siempre como `root`** (así está configurado el VPS).

---

## ⚠️ Antes de empezar: Estrategia de Tests

Lucho tiene **dos tipos de tests**, y NO todos se corren en producción:

| Tipo | Archivo | ¿Corre en PROD? | ¿Por qué? |
|------|---------|:---:|---|
| **Unitarios** | `tests/unit.py` | ✅ SÍ | Sin DB, sin APIs, seguros en cualquier entorno. 550+ tests. |
| **Integración** | `tests/test_integration.py` | ❌ NO | Requiere DB `lucho_test` en puerto 5434 (Docker). Usa credenciales de desarrollo (`lucho:lucho`). Ejecutarlo contra la DB de producción **corrompería datos reales**. |

**Regla de oro**: en el VPS de producción SIEMPRE se corre `python tests/unit.py`. El comando `pytest tests/` NUNCA se usa en producción porque ejecutaría `test_integration.py` contra una DB inexistente (falla) o peor aún, contra la DB real (corrompe datos).

Los tests de integración se corren **solo en desarrollo** (donde existe Docker con `lucho_test`):
```bash
# Solo en máquina de desarrollo
pytest tests/test_integration.py -v
```

---

## 1. Ruta crítica

| Recurso | Ruta / Comando |
|---------|---------------|
| Código fuente | `/root/lucho/app` |
| Virtualenv | `/root/lucho/app/venv` |
| Variables de entorno | `/root/lucho/app/.env` |
| Servicio systemd | `lucho-api` |
| Health check | `http://localhost:8000/health` |
| Logs | `journalctl -u lucho-api` |
| Base de datos | PostgreSQL, user `lucho`, database `lucho` |

---

## 2. Procedimiento completo de actualización

### Paso 1 — Preparar el working tree

```bash
cd /root/lucho/app

# Verificar estado actual
git status
git log --oneline -3

# Guardar cambios locales que pudiera haber (seguridad)
git stash
```

Si `git stash` devuelve "No local changes to save", seguir. Si guardó algo,
anotar con `git stash list` para recuperar después si hace falta.

### Paso 2 — Pull del código nuevo

```bash
git pull origin main
```

Si hay conflicto de merge, abortar y reportar:

```bash
git merge --abort
echo "❌ Conflicto de merge — intervención manual requerida"
exit 1
```

### Paso 3 — Instalar dependencias

```bash
source venv/bin/activate
pip install -r requirements.txt 2>&1 | tail -5
```

Si hay error de dependencias, reportar el error completo y abortar.

### Paso 4 — Backup de la base de datos (OBLIGATORIO)

> 🛡️ **Este paso es obligatorio.** Si el backup falla, ABORTAR. Nunca ejecutar
> migraciones sin un backup reciente. El backup se guarda con timestamp para
> poder identificarlo y restaurarlo fácilmente.

```bash
mkdir -p /root/backups
su - postgres -c "pg_dump lucho" > /root/backups/backup_lucho_pre_deploy_$(date +%Y%m%d_%H%M%S).sql
echo "✅ Backup guardado en /root/backups/"
```

Verificar que el backup no esté vacío:

```bash
BACKUP_FILE=$(ls -t /root/backups/backup_lucho_pre_deploy_*.sql | head -1)
SIZE=$(stat -c%s "$BACKUP_FILE" 2>/dev/null || echo 0)
if [ "$SIZE" -gt 1000 ]; then
    echo "✅ Backup válido: $(basename $BACKUP_FILE) ($SIZE bytes)"
else
    echo "❌ Backup VACÍO o muy pequeño — ABORTAR"
    exit 1
fi
```

### Paso 5 — Ejecutar tests unitarios

> ⚠️ **IMPORTANTE**: Solo se corren tests unitarios (`unit.py`). NO se usa `pytest`
> en producción porque ejecutaría `test_integration.py`, que requiere la base de
> datos `lucho_test` con credenciales de desarrollo (puerto 5434 Docker).
> Ejecutar tests de integración contra la DB de producción **corrompería datos reales**.
> Ver "Estrategia de Tests" al inicio de este documento.

```bash
cd /root/lucho/app
source venv/bin/activate
python tests/unit.py 2>&1
```

| Resultado | Acción |
|-----------|--------|
| ✅ Todos pasan (`FAIL: 0`) | Continuar al paso 6 |
| ❌ `FAIL > 0` | Reportar los fallos, abortar, NO reiniciar |

### Paso 6 — Ejecutar migraciones

```bash
cd /root/lucho/app
source venv/bin/activate
python -m alembic upgrade head 2>&1
```

Si la migración falla:

```bash
echo "❌ Migración fallida. Restaurar backup:"
echo "   su - postgres -c \"psql lucho\" < /root/backups/backup_lucho_pre_deploy_*.sql"
exit 1
```

### Paso 7 — Reiniciar el servicio

```bash
systemctl restart lucho-api
sleep 3
systemctl is-active --quiet lucho-api && echo "✅ Servicio activo" || echo "❌ Servicio CAÍDO"
```

### Paso 8 — Health check

```bash
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Health check: HTTP $HTTP_CODE"
else
    echo "❌ Health check: HTTP $HTTP_CODE"
    journalctl -u lucho-api --since "30 seconds ago" --no-pager
fi
```

### Paso 9 — Verificar logs recientes

```bash
journalctl -u lucho-api --since "1 minute ago" --no-pager | tail -30
```

Revisar que no haya `ERROR`, `Traceback`, ni `FATAL`.

---

## 3. Procedimiento rápido (hotfix trivial)

> ⚠️ **SOLO para cambios que no tocan lógica**: documentación, strings, comentarios.
> Si el cambio toca código Python, modelos, migraciones, o servicios, usar el
> procedimiento COMPLETO de la Sección 2.
>
> Este procedimiento no hace backup. Si hay migraciones nuevas, se ejecutan.

```bash
cd /root/lucho/app
git stash
git pull origin main
source venv/bin/activate
pip install -r requirements.txt 2>&1 | tail -3
python -m alembic upgrade head 2>&1
systemctl restart lucho-api
sleep 3
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8000/health
```

---

## 4. Rollback de emergencia

Si algo falla después del deploy:

```bash
# 1. Restaurar backup
su - postgres -c "psql lucho" < /root/backups/backup_lucho_pre_deploy_YYYYMMDD_HHMMSS.sql

# 2. Volver al commit anterior
cd /root/lucho/app
git log --oneline -5
git reset --hard <commit-anterior>

# 3. Reinstalar dependencias de esa versión
source venv/bin/activate
pip install -r requirements.txt

# 4. Reiniciar
systemctl restart lucho-api
sleep 3
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8000/health
```

---

## 5. Comandos de diagnóstico rápido

```bash
# Estado del servicio
systemctl status lucho-api --no-pager

# Últimos errores
journalctl -u lucho-api --since "5 min ago" --no-pager | grep -i -E "error|traceback|fatal|exception"

# Versión desplegada
cd /root/lucho/app && git describe --tags --always

# Tests unitarios (seguros en producción)
cd /root/lucho/app && source venv/bin/activate && python tests/unit.py

# Tests de integración (SOLO en desarrollo — requiere lucho_test en Docker)
cd /root/lucho/app && source venv/bin/activate && pytest tests/test_integration.py -v

# Conexión a DB
cd /root/lucho/app && source venv/bin/activate && \
  python -c "import asyncio; from app.database import async_session; print('OK')"

# Uso de disco
df -h / | tail -1

# Puertos en escucha
ss -tlnp | grep -E "8000|80|443|5432"
```

---

## 6. Variables de entorno que Pi debe conocer

Estas están en `/root/lucho/app/.env`. Pi nunca debe modificarlas directamente;
solo leerlas si necesita debuggear.

| Variable | Uso |
|----------|-----|
| `DATABASE_URL` | Conexión PostgreSQL |
| `REDIS_URL` | Conexión Redis |
| `TELEGRAM_BOT_TOKEN` | Bot de Telegram |
| `WHATSAPP_*` | WhatsApp Cloud API |
| `ANTHROPIC_API_KEY` | Claude |
| `OPENAI_API_KEY` | Whisper + Embeddings |
| `PAYPHONE_*` | Pasarela de pago |
| `DEUNA_*` | DeUna (Pichincha) |
| `KEY49_*` | Facturación SRI |

---

## 7. Checklist pre-deploy para Pi

Antes de ejecutar el procedimiento completo, Pi debe verificar:

- [ ] `git status` — working tree limpio (o cambios stasheados)
- [ ] `git log origin/main..HEAD` — no hay commits locales sin push
- [ ] `systemctl is-active postgresql redis-server minio nginx` — infraestructura OK
- [ ] `df -h / | tail -1` — al menos 5 GB libres
- [ ] `free -h | head -2` — al menos 1 GB RAM libre

---

## 8. Notas para Pi

- **Siempre ejecutar como root.** No usar `sudo`. El deploy del VPS se hizo
  con root directo según la guía `deploy_vps_debian13.md`.
- **Nunca modificar `.env`** sin autorización explícita de Patricio.
- **Nunca hacer `git push --force`** ni `git reset --hard` sin confirmar.
- **Tests en producción**: solo `python tests/unit.py`. NUNCA uses `pytest`
  a secas en el VPS porque ejecutaría tests de integración que requieren
  `lucho_test` (base de datos de desarrollo en Docker) y podrían corromper
  la base de datos de producción. Ver "Estrategia de Tests" al inicio.
- **Si un test unitario falla, reportar y abortar.** No desplegar código roto.
- **Siempre dejar el servicio corriendo.** Si algo falla a mitad del
  procedimiento, hacer rollback o restaurar el estado anterior.
- **Documentar cada deploy** en `NEXT_SESSION.md` con: tag/commit, cambios,
  tests, y resultado del health check.
