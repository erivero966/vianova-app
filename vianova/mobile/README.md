# Vianova para Android (Capacitor)

La app se distribuye de dos formas, ambas con el mismo código de `frontend/`:

1. **PWA instalable** (ya funciona): al abrir la URL del servidor en Chrome para Android aparece «Instalar app».
   Usa `manifest.webmanifest` y `sw.js`. El service worker nunca guarda en caché respuestas de `/api`.
2. **APK nativo con Capacitor** (esta carpeta): envuelve la misma app en un proyecto Android (`android/`, ya generado).

## Compilar el APK

Requisitos: Node 18+, JDK 17 y Android Studio (SDK 34).

```bash
cd mobile
npm install
# 1) Edite capacitor.config.json → server.url con la URL HTTPS del backend del ambiente que corresponda
#    (pruebas: https://qa.vianova.example.pe · producción: https://vianova.example.pe)
npm run sync          # compila el frontend y lo copia al proyecto Android
npm run open          # abre Android Studio → Build > Build APK(s)
```

- El APK de **pruebas** apunta al servidor de pruebas (datos ficticios); el de **producción**, al de producción.
  Nunca se distribuye un APK de desarrollo a participantes.
- Firma: genere el keystore en Android Studio (Build > Generate Signed Bundle/APK) y guárdelo en el gestor de
  secretos del equipo, nunca en el repositorio ni en discos externos.
- Notificaciones: el plugin `@capacitor/local-notifications` permite programar recordatorios con la app cerrada.

> En el entorno donde se generó este proyecto no había acceso a la descarga de Gradle ni del SDK de Android, por lo
> que el APK debe compilarse en una PC con Android Studio siguiendo los pasos anteriores.
