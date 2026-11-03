# Ciberseguridad — ETAPA 2: ID · Identificar

**Empresa:** AM Digital Web E.I.R.L.  
**Sistema crítico de referencia:** Bus Digital / instalación TopPeru  
**Controles:** ID-01 a ID-07 del Taller 03  
**Fecha de corte:** 20 de octubre de 2026  
**Clasificación:** CONFIDENCIAL  
**Tipo de revisión:** documental y local; sin conexiones ni verificaciones activas

## 1. Objetivo y límites

Esta etapa determina qué evidencia existe sobre inventarios de hardware y software, licencias y shadow IT, clasificación de información, exposición a Internet, análisis de vulnerabilidades, pentesting y análisis de impacto al negocio (BIA). También relaciona los activos identificados con ventas, reservas, facturación SUNAT, pagos y encomiendas de Bus Digital.

No se ejecutaron escaneos, consultas DNS, solicitudes HTTP, conexiones SSH, auditorías de dependencias, validaciones de endpoints, pruebas de credenciales ni accesos a producción. El informe de pentest anterior se utilizó como **fuente secundaria histórica** y no se reprodujo ninguna de sus pruebas.

### Escala de evaluación

| Resultado | Significado |
|---|---|
| ACREDITADA | Evidencia suficiente, vigente y trazable de la dimensión. |
| PARCIALMENTE ACREDITADA | Evidencia real pero incompleta, informal, histórica o de cobertura limitada. |
| NO ACREDITADA | No se proporcionó evidencia suficiente. No demuestra por sí sola inexistencia. |
| NO EVALUABLE | No es posible determinar el funcionamiento con la evidencia disponible. |

Para esta etapa, **existencia formal** exige un inventario, procedimiento, clasificación, programa o análisis aprobado y con responsable. **Operación efectiva** exige actualización, conciliación, revisión periódica, tratamiento y evidencia fechada.

## 2. Fuentes revisadas y reservas

| Ref. | Fuente | Uso | Reserva |
|---|---|---|---|
| I-01 | `ASTI - Taller 03 - Ciberseguridad.docx` | Criterios ID-01 a ID-07. | Guía académica. |
| I-02 | `Ciberseguridad_00_Preparacion.md` y `Ciberseguridad_01_Gobernar.md` | Alcance, fuentes, sistemas, terceros y gobierno. | Documentos de trabajo. |
| I-03 | `Informe_Auditoria_BusDigital_EPIS_Actualizado.docx` | Antecedentes del Taller 02: arquitectura, software, dependencias, datos, backups y continuidad. | Revisión estática al 10/10/2026; no acredita producción. |
| I-04 | `Informe Final.pdf` de prácticas preprofesionales | Observación del área TI: estaciones, tres servidores, red, herramientas, licencias y procesos críticos. | Informe académico; no es inventario corporativo aprobado. |
| I-05 | `Inventario_Arequipa_0101_COMPLETO.xlsx` y copia `(1)` | Inventario de estaciones/periféricos de una agencia Arequipa. | Los dos archivos son idénticos. Propiedad, fecha de corte y relación con AM Digital no acreditadas. |
| I-06 | `reporte_simple_pentest_topperu.docx` y copia `(1)` | Fuente secundaria de superficie y vulnerabilidades al 14/06/2026. | Copias idénticas; borrador académico Grey Box, no pentest profesional ni estado actual. Incluyó revisión local y algunas validaciones públicas en su fecha. |
| I-07 | `API-TOPPERU.yaml` y documentación HTML local | Existencia de una colección de API de producción/local y procesos de reserva/venta. | El archivo contiene material sensible; se revisó de forma local y sanitizada. No se usó para enviar solicitudes. |
| I-08 | `Informe_Seguridad_Informatica_Bus_Digital.docx` / `INFORME PISTAS DE AUDITORIA.pdf` | Componentes, datos y trazabilidad en instancia local. | Laboratorio; no representa producción. |
| I-09 | `gerencial-informe.pdf`, `tecnico-informe.pdf` y ZIP `INFORMES-PENTEST` | Verificación de pertinencia. | Corresponden a **Global Megatic**, no a AM Digital; excluidos de la evaluación. |
| I-10 | `Informe_Modelo_Pentest_Superficie_Exposicion_TNagata*.docx` | Verificación de pertinencia. | Modelo simulado TNagata; excluido como evidencia. |

### Nota sobre duplicados

- Las dos copias del pentest TopPeru tienen el mismo hash SHA-256; constituyen una sola fuente.
- Las dos copias del inventario Arequipa también tienen el mismo hash SHA-256; constituyen una sola fuente.
- La duplicación de archivos no aumenta la suficiencia ni independencia de la evidencia.

## 3. Resumen de ID-01 a ID-07

| Control | Existencia formal | Operación efectiva | Conclusión documental |
|---|---|---|---|
| ID-01 · Inventario de hardware | NO ACREDITADA | PARCIALMENTE ACREDITADA | Se conocen activos por informes y existe un inventario de agencia no atribuido; no hay inventario maestro vigente de AM Digital. |
| ID-02 · Software, licencias y shadow IT | PARCIALMENTE ACREDITADA | PARCIALMENTE ACREDITADA | Existe una matriz académica de herramientas/licencias y uso observado; faltan inventario aprobado, responsables, conciliación y control de shadow IT. |
| ID-03 · Clasificación de información | NO ACREDITADA | NO ACREDITADA | Se identifican tipos de datos, pero no esquema, propietarios, etiquetado, retención ni manejo uniforme. |
| ID-04 · Servicios expuestos | NO ACREDITADA | PARCIALMENTE ACREDITADA | Hay una fotografía histórica de exposición y arquitectura, pero no una relación vigente declarada/validada por TI. |
| ID-05 · Análisis de vulnerabilidades | NO ACREDITADA | PARCIALMENTE ACREDITADA | Se documentó una revisión puntual, incluidas dependencias, sin programa periódico, seguimiento o cierre acreditado. |
| ID-06 · Pentesting | PARCIALMENTE ACREDITADA | PARCIALMENTE ACREDITADA | Existe un borrador Grey Box de junio de 2026; no se acreditaron autorización específica, aceptación corporativa, remediación ni retest. |
| ID-07 · BIA | NO ACREDITADA | NO ACREDITADA | Los procesos críticos e impactos están descritos cualitativamente, pero no existe BIA aprobado con MTPD, RTO/RPO y dueños. |

**Resultado:** 0 de 7 controles acreditan simultáneamente existencia formal y operación efectiva. La mejor cobertura está en la identificación técnica informal de software, exposición histórica y procesos críticos; los mayores vacíos están en propiedad, vigencia, clasificación, periodicidad y aprobación.

## 4. Matriz consolidada de activos críticos

La criticidad es preliminar y sirve para ordenar la validación con TI y negocio; no reemplaza un BIA.

| Activo / grupo | Tipo y entorno conocido | Operaciones de Bus Digital relacionadas | Información / dependencia | Impacto si falla o se compromete | Propietario confirmado | Criticidad preliminar | Evidencia y validación pendiente |
|---|---|---|---|---|---|---|---|
| Aplicación Bus Digital / TopPeru | Aplicación web Laravel; producción cloud según I-04 | Consulta, reservas, venta, asientos, caja, reportes, encomiendas y administración | Depende de BD, Cloudflare, servidor web, pagos y SUNAT | Detención de ventas y operaciones; alteración o exposición de datos | No; TI la opera | CRÍTICA | I-03/I-04/I-06. Confirmar instalaciones, clientes, responsable y SLA. |
| Base de datos MySQL/MariaDB | BD relacional; versión/topología productiva no validadas en esta etapa | Reserva y estado de asientos, pasajeros, pagos, comprobantes, caja, liquidaciones y encomiendas | Datos personales, comerciales, tributarios y operativos | Pérdida de integridad/disponibilidad; fraude, duplicidad, sanción y paralización | No | CRÍTICA | I-03/I-06. Confirmar motor, host, réplicas, cuentas, tamaño y respaldo. |
| Portal y API de venta/reserva | Frontend web y API | Ciudades, itinerarios, croquis, bloqueo de asiento y confirmación de venta | Datos de viaje/pasajero; autenticación de integraciones | Exposición de datos, abuso de reservas, interrupción del canal digital | No | CRÍTICA | I-06/I-07. Confirmar endpoints vigentes, dueño y autenticación. |
| Punto de venta / módulos de agencia | Web/POS, equipos y periféricos | Venta presencial, impresión, cobro y control de atención | Estaciones, impresoras híbridas, pin pads y lectoras | Imposibilidad de vender/cobrar/imprimir; fraude local | No | ALTA | I-05/I-06. Confirmar si inventario Arequipa pertenece a un cliente y quién lo administra. |
| Reservas y asientos | Módulo lógico y tablas | Selección, bloqueo, liberación, venta, reprogramación y migración de pasajeros | Consistencia transaccional y concurrencia | Sobreventa, doble asignación, reclamos y pérdida de ingresos | No | CRÍTICA | I-03/I-08. Confirmar dueño de proceso y controles productivos. |
| Facturación electrónica / SUNAT–Greenter | Integración externa y módulos/rutas internos | Emisión, reenvío, anulación y consulta de comprobantes | Datos tributarios, correlativos, XML/PDF, colas | Incumplimiento tributario, ventas sin comprobante, desalineación tras recuperación | No | CRÍTICA | I-03/I-04/I-06. Confirmar proveedor, contrato, credenciales, SLA y contingencia. |
| Pasarelas de pago | Mercado Pago/Culqi y otras por confirmar; cuenta por cliente | Cobro en línea, confirmación y conciliación | Tokens/credenciales, importes y estados | Fraude, cobro sin venta o venta sin cobro, interrupción | Cuenta del cliente según I-04; responsable interno no confirmado | CRÍTICA | I-04. Confirmar matriz por cliente, accesos y conciliación. |
| Encomiendas / carga | Módulo Bus Digital | Registro, seguimiento, pago, comprobante y entrega | Remitente, destinatario, contenido y estado | Pérdida de trazabilidad, reclamos y exposición de datos | No | ALTA | I-03/I-04. Confirmar arquitectura, dueño y RTO. |
| Servidores cloud Hetzner | Tres servidores descritos: Bus Digital, nuevo proyecto y pruebas | Alojamiento de aplicaciones/BD/servicios según distribución real | Dependencia de red, SO, almacenamiento y accesos SSH | Caída de múltiples servicios; acceso privilegiado | TI opera; propietario formal no confirmado | CRÍTICA | I-04. Confirmar inventario, ubicación lógica, propósito, recursos y segregación. |
| Cloudflare / DNS / CDN / proxy | SaaS frontal | Resolución de dominios, publicación, proxy y protección básica | Dominios, certificados y reglas de tráfico | Indisponibilidad o desvío de todos los canales públicos | TI opera | CRÍTICA | I-04. Confirmar cuentas, MFA, propietarios y plan de recuperación DNS. |
| GitHub y repositorios | SaaS de código; plan Free observado | Desarrollo, ramas por cliente, cambios y despliegue | Código, historial, configuración y posible acceso a secretos | Alteración de software, fuga de código y compromiso de despliegues | TI opera | ALTA | I-03/I-04. Confirmar organización, repositorios, miembros, MFA y protección de ramas. |
| Estaciones de trabajo y LAN de oficina | Aproximadamente 10 PCs, Wi-Fi compartido y router del ISP según I-04 | Desarrollo, soporte, acceso administrativo y tratamiento de información | Código, credenciales, copias y sesiones privilegiadas | Punto de entrada hacia nube y clientes; pérdida de secretos | No | ALTA | No hay inventario individual, EDR, cifrado ni propiedad confirmados. |
| Backups y artefactos de recuperación | Volcados SQL locales y mecanismos productivos no acreditados | Recuperación de BD y continuidad | Copia integral de información crítica | Pérdida definitiva o exposición masiva | No | CRÍTICA | I-03 y archivos locales. Confirmar plataforma, custodio, cifrado, retención y pruebas. |
| Documentación técnica y colecciones API | YAML/HTML/Docusaurus/archivos locales | Integraciones, soporte y despliegue | Endpoints, ejemplos, credenciales y datos de prueba | Facilita acceso indebido si se comparte o pierde | No | ALTA | I-04/I-07. Clasificar, retirar secretos, asignar propietario y controlar acceso. |
| Correo, mensajería y notificaciones | WhatsApp, Brevo/Mailjet, Pusher y servicios por confirmar | Soporte, alertas, comprobantes y comunicación con clientes | Mensajes, enlaces, datos de contacto y recuperación de cuentas | Phishing, fuga de información y pérdida de trazabilidad | No | ALTA | I-03/I-04. Confirmar plataformas vigentes, cuentas, retención y administración. |

### Flujo crítico resumido

```text
Cliente / operador
      │
      ▼
Portal web / POS / API
      │
      ├── consulta itinerario y disponibilidad ──► Base de datos
      ├── bloquea/confirma reserva y asiento ────► Base de datos
      ├── procesa pago ──────────────────────────► Pasarela del cliente
      ├── confirma venta y registra caja ────────► Base de datos
      ├── emite comprobante ─────────────────────► SUNAT / Greenter
      ├── imprime/notifica ──────────────────────► Periféricos / correo / mensajería
      └── registra encomienda, si aplica ────────► Módulo de carga y trazabilidad

Servicios transversales: Hetzner · Cloudflare · GitHub · accesos SSH · backups · logs
```

Un fallo en BD, alojamiento, DNS/proxy, pagos o facturación puede interrumpir o desalinear el proceso completo. La dependencia y el impacto se encuentran descritos, pero tiempos tolerables, prioridades de recuperación y responsables requieren un BIA formal.

## 5. Matriz de exposición declarada/documental

No existe todavía una relación firmada por TI. Esta matriz consolida lo **declarado en informes** y la fotografía histórica de I-06. Debe ser validada sin escaneo por el responsable de TI. Se omiten FQDN, IP, usuarios y rutas sensibles.

| Servicio / superficie | Exposición indicada | Función | Fuente y fecha | Estado actual | Riesgo o reserva | Confirmación requerida de TI |
|---|---|---|---|---|---|---|
| Frontend Bus Digital / TopPeru | Internet vía Cloudflare | Venta, reserva y operación web | I-04; I-06 al 14/06/2026 | NO CONFIRMADO | Activo crítico público y multicliente | Dominio/instancia vigente, dueño, WAF/proxy y autenticación. |
| API de venta/reserva | Internet; colección de producción documentada | Itinerarios, croquis, reserva/bloqueo y venta | I-06/I-07 | NO CONFIRMADO | El pentest reportó rutas con respuesta sin login; no se revalidó | Lista oficial de APIs, cuáles son públicas, método de autenticación y datos devueltos. |
| API/módulo Cargo | Internet según arquitectura/pentest | Operaciones de carga/encomiendas | I-03/I-06 | NO CONFIRMADO | Hardening de login y cobertura de autorización quedaron cuestionados | URL lógica, audiencia, rate limit, MFA y permisos. |
| POS y API POS | Internet según pentest histórico | Venta en puntos de atención | I-06 al 14/06/2026 | NO CONFIRMADO | Superficie adicional por cliente/agencia | Necesidad, aislamiento, autenticación y responsable. |
| Facturación y rutas de prueba SUNAT | Internet según pentest histórico | Comprobantes y soporte de facturación | I-06 al 14/06/2026 | NO CONFIRMADO | Rutas de prueba fueron calificadas como hallazgo pendiente | Confirmar retiro/protección y separar pruebas de producción. |
| Interfaz de administración de BD | Página pública observada históricamente; no se intentó login | Administración de BD | I-06 al 14/06/2026 | NO CONFIRMADO | Exposición administrativa innecesaria si continúa | Confirmar si existe; restricción por VPN/allowlist y registro de acceso. |
| Servicio SSH de servidores cloud | Acceso directo desde Internet, sin VPN, según I-04 | Despliegue y administración | I-04, periodo ene.–jun. 2026 | NO CONFIRMADO | Alto privilegio; credenciales/llaves compartidas informalmente | Hosts autorizados, allowlist/VPN, MFA, llaves, usuarios y logs. |
| Base de datos | Puerto indicado como local solamente en I-06 | Persistencia | I-06 al 14/06/2026 | NO CONFIRMADO | No debe inferirse exposición pública | Confirmar bind, firewall, red privada y consumidores autorizados. |
| Servidor/ambiente de pruebas | Versión pública de pruebas mencionada | Validación previa | I-04 | NO CONFIRMADO | Riesgo de datos/secretos productivos y controles más débiles | URL lógica, aislamiento, datos, acceso y fecha de eliminación. |
| Cloudflare/DNS/CDN/proxy | Internet por definición | Publicación y protección frontal | I-04 | PROBABLE, NO VALIDADO | Dependencia crítica y cuenta privilegiada | Dominios cubiertos, bypass de origen, responsables, MFA y alertas. |
| Documentación privada | Proxy con login según I-04 | Guías técnicas del nuevo ecosistema | I-04 | NO CONFIRMADO | Puede contener arquitectura y despliegue | Ubicación, autenticación, usuarios, clasificación y respaldo. |
| Correo/mensajería/webhooks | Internet por integración | Notificaciones, soporte y automatización | I-03/I-04 | NO CONFIRMADO | Tokens, datos personales y disponibilidad de terceros | Proveedores vigentes, endpoints, propietarios, secretos y monitoreo. |

### Fotografía histórica del pentest TopPeru

I-06 registra, al 14 de junio de 2026, 13 resultados: 4 altos, 6 medios y 3 bajos. Sus temas fueron control de acceso de APIs, modo debug, dependencias vulnerables, rutas de prueba, interfaz administrativa de BD, cabeceras, autenticación de Cargo, logging excesivo, CORS, cookies, listado de directorios, secretos y credenciales de ejemplo. Todos aparecían abiertos o pendientes en el borrador.

Estos resultados:

- no se consideran automáticamente vigentes al 20/10/2026;
- no fueron revalidados en esta etapa;
- no acreditan una declaración oficial de exposición por TI;
- no deben difundirse fuera del canal autorizado;
- requieren evidencia de remediación y retest, no una repetición no autorizada.

## 6. Evaluación por control

### ID-01 · Inventario actualizado de hardware

**Existencia formal:** **NO ACREDITADA.**  
I-04 describe aproximadamente 10 PCs, Wi-Fi/router de oficina y tres servidores Hetzner. I-05 declara 44 impresoras híbridas, 33 pin pads y 56 lectoras de cheques de una agencia Arequipa, además de nombres de estaciones. No se acreditó que I-05 pertenezca a AM Digital, esté vigente o sea administrado por ella; por tanto, no puede integrarse al inventario corporativo.

**Operación efectiva:** **PARCIALMENTE ACREDITADA.**  
El equipo conocía y operaba servidores, estaciones y red, pero no se observa un inventario maestro con propietario, custodio, estado, ubicación, criticidad, ciclo de vida y conciliación. I-05 contiene 42 asignaciones de nombre de estación, 37 nombres únicos, cinco nombres repetidos y 36 filas “sin estación asignada”; esas características exigen depuración antes de usarlo como control.

**Evidencia:** I-04, I-05 y matriz de activos de este informe.

**Brecha preliminar:** activos cloud, estaciones, red, móviles, periféricos, equipos de clientes y activos virtuales no están reunidos en una fuente corporativa confiable. No se distingue propiedad de AM Digital, del proveedor o del cliente.

**Preguntas para TI:**

1. ¿Cuál es el inventario maestro vigente y quién lo actualiza/aprueba?
2. ¿Qué activos son de AM Digital, cuáles de clientes y cuáles arrendados al proveedor?
3. ¿Cuáles son los tres servidores descritos, qué alojan y qué identificador/propietario tienen?
4. ¿Cuántas estaciones, laptops, móviles, routers, switches, impresoras, cámaras y UPS existen?
5. ¿El inventario Arequipa corresponde a un cliente de Bus Digital y AM Digital administra alguno de esos equipos?
6. ¿Cómo se concilia el inventario con nube, compras, bajas y observación física?

### ID-02 · Inventario de software, licencias y shadow IT

**Existencia formal:** **PARCIALMENTE ACREDITADA.**  
I-04 contiene una matriz académica con GitHub Free (~10 usuarios), Asana Free (~5), Cloudflare Free, Figma Free (~3), tres servidores Hetzner y cuentas de pasarela por cliente. También enumera Laravel, PHP, Angular, NestJS, Flutter, Node.js, Docker, MySQL/MariaDB, Git, Visual Studio Code y servicios externos. No tiene propietario, fecha de recertificación, equipos/servidores asociados, facturas ni aprobación corporativa.

**Operación efectiva:** **PARCIALMENTE ACREDITADA.**  
El uso de esas herramientas fue observado durante prácticas. Sin embargo, WhatsApp era el canal principal, Asana se usaba parcialmente, no había correo corporativo ni gestor centralizado de contraseñas, y se entregaban accesos informalmente. Esto evidencia shadow IT o, al menos, herramientas y cuentas sin gobierno formal. La documentación local también incluye volcados SQL, archivos de entorno y una colección API con material de autenticación y datos de ejemplo; no se abrieron los secretos adicionales ni se reproducen aquí.

**Evidencia:** I-03, I-04, I-07 y listado local sanitizado.

**Brecha preliminar:** falta un catálogo de aplicaciones/SaaS, licencias, versiones, dueños, usuarios, costo, datos tratados, SSO/MFA, aprobación, renovación y baja. No hay mecanismo acreditado para descubrir o regular software, cuentas personales, mensajería y copias locales no autorizadas.

**Preguntas para TI:**

1. ¿Existe inventario de software instalado, dependencias, SaaS, dominios y licencias?
2. ¿Qué herramientas están autorizadas para mensajería, archivos, secretos, tareas y soporte remoto?
3. ¿Se permiten cuentas personales en GitHub, correo, WhatsApp, Cloudflare o paneles de pago?
4. ¿Cómo se detecta software no autorizado y quién aprueba excepciones?
5. ¿Qué planes/licencias están a nombre de AM Digital y cuáles a nombre de clientes o personas?
6. ¿Dónde deben almacenarse colecciones API, volcados SQL, archivos `.env` y documentación sensible?
7. ¿Cómo se revocan licencias y accesos al cesar un trabajador o practicante?

### ID-03 · Clasificación y localización de información

**Existencia formal:** **NO ACREDITADA.**  
No se entregó política o esquema de clasificación, inventario de información, propietarios, reglas de etiquetado, retención o eliminación. I-03 identifica datos de pasajeros, menores, contacto, domicilio, viajes, pagos, comprobantes y personal, pero esto es un análisis del modelo, no una clasificación corporativa.

**Operación efectiva:** **NO ACREDITADA.**  
La presencia local de SQL, archivos de entorno y una colección API con endpoints, material de autenticación y datos personales de ejemplo indica que información de distinta sensibilidad puede coexistir sin etiquetas ni controles evidentes. No se copiaron los secretos en este informe. El uso de WhatsApp para compartir credenciales refuerza la necesidad de reglas de manejo.

**Evidencia:** I-03, I-04, I-07 y existencia de artefactos locales sensibles.

**Brecha preliminar:** AM Digital no demuestra conocer, por un registro aprobado, dónde reside cada categoría, quién es propietario, por cuánto tiempo se conserva, quién accede y cómo se protege/elimina. No hay separación acreditada entre datos productivos, pruebas y ejemplos.

**Preguntas para TI:**

1. ¿Qué niveles de clasificación utiliza la empresa y quién es dueño de cada conjunto de datos?
2. ¿Dónde residen datos de pasajeros, menores, pagos, comprobantes, encomiendas, trabajadores, logs y backups?
3. ¿Qué datos productivos pueden copiarse a desarrollo o equipos personales y bajo qué autorización?
4. ¿Cómo se etiquetan, cifran, retienen y eliminan volcados, logs, documentos y colecciones API?
5. ¿Existe un repositorio aprobado para secretos y documentación técnica?
6. ¿Cómo se diferencian datos del cliente, de AM Digital y del usuario final?

### ID-04 · Servicios expuestos a Internet declarados por TI

**Existencia formal:** **NO ACREDITADA.**  
No se proporcionó un registro oficial de exposición firmado o validado por TI. La matriz de la sección 5 se reconstruyó a partir de I-04, I-06 e I-07.

**Operación efectiva:** **PARCIALMENTE ACREDITADA.**  
Las fuentes permiten identificar frontends, APIs, POS, facturación, pruebas, Cloudflare y acceso SSH. I-06 documentó una fotografía de junio, pero la vigencia y remediación no están confirmadas. El inventario debe ser declarado por TI sin que el auditor realice descubrimiento activo.

**Evidencia:** matriz de exposición de este informe; I-04, I-06 e I-07.

**Brecha preliminar:** falta una única relación vigente de dominios/subdominios, IP/hosting, servicio, ambiente, dueño, propósito, método de autenticación, datos, proveedor, criticidad, fecha de revisión y excepción. Tampoco se acredita detección de activos olvidados o shadow IT externo.

**Preguntas para TI:**

1. ¿Puede TI validar o corregir cada fila de la matriz de exposición sin ejecutar un nuevo escaneo?
2. ¿Qué dominios, APIs, paneles, puertos administrativos y ambientes de prueba siguen publicados?
3. ¿Cuál es el dueño de cada servicio y su justificación de negocio?
4. ¿Hay acceso directo al origen que evite Cloudflare?
5. ¿Qué paneles administrativos exigen VPN, allowlist, MFA o Zero Trust?
6. ¿Cómo se detectan y retiran subdominios, certificados y servicios abandonados?

### ID-05 · Análisis periódicos de vulnerabilidades

**Existencia formal:** **NO ACREDITADA.**  
No se encontró política, calendario, alcance recurrente, herramienta aprobada, responsable, SLA de remediación ni tablero de vulnerabilidades. I-06 describe una revisión puntual de código, dependencias y superficie; no acredita un programa.

**Operación efectiva:** **PARCIALMENTE ACREDITADA.**  
El pentest histórico incluyó `composer audit`/`npm audit` y registró dependencias vulnerables. G-03/I-03 también identificó componentes fuera de soporte por revisión estática. No existe evidencia de repetición, priorización, excepciones, correcciones, verificación de cierre o cobertura de todos los activos.

**Evidencia:** I-03 e I-06, únicamente como antecedentes.

**Brecha preliminar:** actividad aislada y académica, sin ciclo de gestión de vulnerabilidades basado en activos y riesgo. No se acredita análisis de infraestructura interna, endpoints, nube, repositorios, imágenes, secretos o configuraciones como programa continuo.

**Preguntas para TI:**

1. ¿Existe calendario de análisis y qué activos/capas cubre?
2. ¿Quién autoriza, ejecuta, recibe y da seguimiento a los resultados?
3. ¿Cuáles son los SLA por severidad y cómo se gestionan excepciones?
4. ¿Se integran SCA, análisis de secretos, imágenes y dependencias al CI/CD?
5. ¿Qué evidencia demuestra cierre de los resultados de junio de 2026?
6. ¿Se mantiene un registro histórico de vulnerabilidades, antigüedad y riesgo residual?

### ID-06 · Pruebas de penetración y remediación

**Existencia formal:** **PARCIALMENTE ACREDITADA.**  
I-06 es un documento real fechado 14/06/2026, denominado “Reporte simple para trabajo académico”, versión 1.0 y estado “Borrador para apoyo del trabajo”. Indica modalidad Grey Box, repositorio local, servidor productivo en modo lectura y validaciones públicas no destructivas. No es un informe profesional completo, no incluye carta de autorización en el propio expediente y no acredita aceptación corporativa.

**Operación efectiva:** **PARCIALMENTE ACREDITADA.**  
La revisión produjo 13 resultados y recomendaciones, pero todos figuraban abiertos o pendientes. No se encontró plan aprobado, responsables, evidencias de cierre ni retest. La autorización del Taller 02 descrita en I-03 es de octubre de 2026 y no puede presumirse retroactivamente como autorización del pentest de junio.

**Evidencia:** I-06; referencias secundarias de I-03. Los informes Global Megatic y el modelo TNagata fueron excluidos.

**Brecha preliminar:** no se acredita un proceso formal de contratación/autorización, reglas de enfrentamiento, alcance aprobado por propietario, protección de evidencias, aceptación de resultados, remediación y retest independiente.

**Preguntas para TI:**

1. ¿AM Digital autorizó por escrito la revisión de junio y cuál fue su alcance exacto?
2. ¿El borrador fue recibido/aceptado por TI o gerencia y existe una versión final?
3. ¿Qué resultados fueron corregidos, aceptados o descartados como falso positivo?
4. ¿Existe evidencia de cierre y retest por persona distinta a quien corrigió?
5. ¿Qué activos de clientes estaban cubiertos y contaban con autorización del propietario?
6. ¿Cuándo se planifica la siguiente prueba y quién definirá las reglas de enfrentamiento?

### ID-07 · BIA de procesos y activos críticos

**Existencia formal:** **NO ACREDITADA.**  
No se entregó BIA aprobado. I-04 identifica Bus Digital, SUNAT, pasarelas e infraestructura cloud como procesos críticos y describe impactos económicos, operativos, tributarios y reputacionales. I-03 señala ausencia de RPO/RTO documentados. Estas descripciones son insumos, no un BIA.

**Operación efectiva:** **NO ACREDITADA.**  
No se conocen MTPD, RTO, RPO, mínimo nivel de servicio, orden de recuperación, dependencias validadas, dueños de proceso, escenarios, volúmenes, estacionalidad o aprobación del negocio. La criticidad de la matriz de activos es preliminar.

**Evidencia:** I-03, I-04 y matriz de activos de este informe.

**Brecha preliminar:** las prioridades tecnológicas parecen basarse en experiencia operativa, sin un análisis empresarial cuantificado que gobierne arquitectura, backups, contratos y recuperación.

**Preguntas para TI y negocio:**

1. ¿Quiénes son los dueños de ventas, reservas, pagos, SUNAT y encomiendas?
2. ¿Cuánto tiempo puede detenerse cada proceso antes de un impacto inaceptable (MTPD)?
3. ¿Qué RTO y RPO exige cada cliente/contrato y qué se ha probado realmente?
4. ¿Cuál es el volumen mínimo de operación y qué procesos manuales alternos existen?
5. ¿Qué dependencias internas y externas requiere cada proceso para recuperarse?
6. ¿Cómo varía el impacto por horario, temporada, cierre tributario o campaña comercial?
7. ¿Qué orden de recuperación ha aprobado gerencia y cuándo se revisó?

## 7. Preguntas consolidadas prioritarias para TI

### Prioridad 1 · Delimitar activos y exposición

1. Entregar el inventario maestro de hardware, activos cloud y activos virtuales, separando propiedad de AM Digital, clientes y proveedores.
2. Validar la matriz de activos críticos y asignar propietario técnico y dueño de negocio.
3. Validar la matriz de exposición documental, indicando qué servicios siguen vigentes, ambiente, dueño y protección.
4. Confirmar la distribución real de aplicaciones, BD, pruebas y backups entre los tres servidores mencionados.
5. Confirmar si el inventario Arequipa pertenece a un cliente y si AM Digital administra estaciones o periféricos.

### Prioridad 2 · Software, datos y shadow IT

6. Entregar inventario de software/SaaS/licencias con usuarios, dueños, versiones, costos, datos y fecha de recertificación.
7. Identificar cuentas personales, mensajería, repositorios, nubes y herramientas no aprobadas utilizadas para trabajo.
8. Definir repositorios autorizados para secretos, volcados, archivos de entorno, colecciones API y documentación.
9. Entregar la política/esquema de clasificación y mapa de información por producto/cliente.
10. Confirmar eliminación o saneamiento de credenciales y datos personales en colecciones y archivos compartidos.

### Prioridad 3 · Vulnerabilidades, pentest y BIA

11. Entregar programa/calendario de vulnerabilidades, responsables, cobertura y SLA de remediación.
12. Proporcionar autorización, versión final, plan de acción y retest del pentest TopPeru de junio.
13. Informar el estado de los 13 resultados históricos sin pedir al equipo auditor que los revalide activamente.
14. Entregar BIA aprobado o convocar a los dueños de proceso para elaborarlo, con MTPD/RTO/RPO y dependencias.
15. Relacionar los requisitos de disponibilidad y recuperación con contratos/SLA de clientes y proveedores.

## 8. Conclusión de la función Identificar

AM Digital cuenta con conocimiento técnico práctico de sus productos, herramientas e infraestructura, y la documentación permite reconstruir un mapa útil de Bus Digital. También existe una revisión Grey Box histórica que identifica superficie y riesgos. Sin embargo, la identificación depende de informes académicos, conocimiento de personas y archivos dispersos, no de registros corporativos vigentes y aprobados.

Las brechas dominantes son: falta de inventario maestro con propiedad y ciclo de vida; catálogo incompleto de software/licencias y shadow IT; ausencia de clasificación de información; exposición no validada por TI; análisis de vulnerabilidades no periódico; pentest sin cierre acreditado; y ausencia de BIA formal. Los datos de junio y del Taller 02 deben usarse para orientar la validación, nunca como prueba automática del estado actual.

## 9. Punto de detención

La ETAPA 2 finaliza aquí. No se efectuaron verificaciones activas ni conexiones a sistemas remotos, no se repitió el pentest y no se iniciaron los controles PR, DE, RS o RC.
