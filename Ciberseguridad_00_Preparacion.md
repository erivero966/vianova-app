# Ciberseguridad — ETAPA 0: preparación

**Empresa:** AM Digital Web E.I.R.L.  
**Sistema de referencia:** Bus Digital / repositorio local identificado como TopPeru  
**Marco:** NIST Cybersecurity Framework (CSF) 2.0, según los 46 puntos de control definidos en la guía del Taller 03  
**Fecha de corte:** 20 de octubre de 2026  
**Clasificación:** CONFIDENCIAL — documento de preparación; no contiene una conclusión de auditoría

## 1. Propósito y límite de esta etapa

Esta ETAPA 0 consolida únicamente la información ya disponible, reconstruye el alcance preliminar, prepara la matriz base de los 46 controles y organiza las solicitudes de evidencia y autorizaciones. No evalúa todavía la eficacia de los controles, no asigna niveles de madurez, no formula hallazgos definitivos y no inicia los demás controles del Taller 03.

Durante esta preparación **no se ejecutaron** escaneos, consultas DNS, conexiones a sistemas, consultas SQL, pruebas HTTP, revisiones de producción, restauraciones, cambios de configuración, captura de tráfico, phishing simulado ni ninguna otra verificación activa. La revisión fue exclusivamente documental y local.

## 2. Fuentes revisadas y valor probatorio

| Ref. | Fuente | Contenido reutilizable | Reserva / limitación |
|---|---|---|---|
| F-01 | `ASTI - Taller 03 - Ciberseguridad.docx` | Alcance, metodología, reglas éticas, 46 puntos de control, encuesta, recorrido, madurez y estructura del entregable. | Es la guía de trabajo, no evidencia de AM Digital. |
| F-02 | `ASTI - Taller 02 - Base de Datos.docx` | Criterios y controles previos de BD; vínculos con altas/bajas, backups, continuidad, documentación y normas. | Es la guía anterior, no evidencia de operación. |
| F-03 | `Informe_Auditoria_BusDigital_EPIS_Actualizado.docx` | Revisión estática del repositorio TopPeru/Bus Digital; arquitectura lógica; 52/61 controles investigados; riesgos preliminares y evidencias F1-EV a F6-EV. | Informe preliminar al 10/10/2026. No hubo entrevistas formales, consultas SQL ni inspección de producción. “Parcialmente verificado” no acredita operación productiva. DOC/NOR y 21 pruebas DAT quedaron pendientes. |
| F-04 | `Informe_Seguridad_Informatica_Bus_Digital.docx` | Evidencia de trazabilidad, logs y transacciones en una instancia local de demostración; riesgos de visores, rutas de prueba y datos sensibles en registros. | No corresponde a producción. La instancia local usó MariaDB 10.4.28 y no demuestra la configuración de AM Digital ni la de sus clientes. |
| F-05 | `AM-Digital-Web-EIRL.pptx.pdf` | Historia, oferta, productos, estructura directiva resumida, clientes y proveedores/alianzas declarados. | Presentación corporativa; requiere confirmación de vigencia y respaldo documental. |
| F-06 | `El-Proceso-CORE-de-Negocio.pptx.pdf` | Flujo core de Bus Digital, responsables, tecnología, dependencias, riesgos y KPIs propuestos. | Descripción de proceso; no acredita controles ni configuraciones actuales. |
| F-07 | `Inventario_Arequipa_0101_COMPLETO.xlsx` y copia `(1)` | Inventario de una agencia Arequipa: estaciones de trabajo, impresoras híbridas, pin pads y lectoras de cheques. Totales declarados: 44, 33 y 56, respectivamente. | Los dos archivos parecen duplicados. No se ha acreditado propietario, cliente, fecha de actualización ni relación exacta con AM Digital/Bus Digital. Contiene identificadores de activos que deben tratarse como confidenciales. |
| F-08 | Solicitud/autorización del 05/10/2026 descrita en F-03 | Autorización previa declarada para consultas `SELECT`, bajo supervisión de TI y con fines académicos. | No se verificó independientemente la firma. Su alcance no cubre por defecto entrevistas, encuesta, recorrido, visualización de configuraciones ni el Taller 03 completo. |

### Regla de uso de la evidencia heredada

- **Hecho conocido:** consta directamente en una fuente y se limita al ambiente allí indicado.
- **Indicio reutilizable:** orienta la solicitud o la entrevista, pero debe confirmarse en el entorno vigente.
- **Pendiente:** no existe evidencia suficiente para decidir existencia formal u operación efectiva.
- La ausencia de un documento en el repositorio **no demuestra** que la empresa carezca de él.
- La evidencia de una instancia local **no debe trasladarse** a producción.

## 3. Alcance organizacional reconstruido

### 3.1 Organización y propósito

AM Digital Web E.I.R.L. es presentada como una empresa de desarrollo de soluciones digitales fundada en 2018, con sede/presencia en Arequipa y servicios de desarrollo web, comercio electrónico, hosting, APIs, automatización, marketing digital e integraciones. Su producto principal para el sector de transporte interprovincial es **Bus Digital**.

La estructura directiva disponible solo permite reconocer, por cargo, una **Gerencia/CEO**, una **Dirección de Tecnología** y una **función comercial**. No se dispone todavía de organigrama vigente, número total de trabajadores, responsables formales de seguridad, administración de infraestructura, DBA, soporte, RR. HH., protección de datos, continuidad ni respuesta a incidentes.

### 3.2 Unidades, personas y ubicaciones preliminarmente incluidas

- Alta dirección y gerencia de AM Digital.
- Dirección de Tecnología, desarrollo, soporte e infraestructura.
- Función comercial y atención a clientes.
- RR. HH. o quien administre altas, cambios y ceses del personal.
- Personal usuario de correo, equipos, repositorios, nube, sistemas administrativos y Bus Digital.
- Sede principal de AM Digital y, solo cuando se confirme su relación contractual y técnica, infraestructura alojada en terceros.
- Instalaciones de clientes quedan **fuera del alcance por defecto**. El inventario de la agencia Arequipa solo podrá incorporarse si se acredita autorización del propietario y relación con el servicio evaluado.

### 3.3 Frontera propuesta para el Taller 03

La guía define como alcance la infraestructura tecnológica de la sede principal: servidores, estaciones, red, correo, accesos remotos, nube, personas y procesos de seguridad. Para AM Digital se propone incluir:

1. Gobierno, riesgos, normativa, presupuesto, terceros y reportes a dirección.
2. Activos de AM Digital que soportan su operación y la prestación de Bus Digital.
3. Identidades de personal y terceros, correo, repositorios, herramientas de soporte y accesos administrativos.
4. Desarrollo, despliegue y operación del producto Bus Digital en lo que sea administrado por AM Digital.
5. Logs, alertas, respuesta a incidentes, backups y recuperación de esos activos.
6. Seguridad física de la sede y del rack/cuarto técnico, si existen.

Quedan fuera hasta contar con autorización expresa: redes y equipos de clientes, producción de transportistas, proveedores administrados exclusivamente por terceros, datos personales identificables y cualquier prueba activa.

## 4. Sistemas, servicios, terceros y dependencias

### 4.1 Sistemas y servicios críticos preliminares

| Prioridad preliminar | Sistema / servicio | Función de negocio | Información o impacto | Estado de conocimiento |
|---|---|---|---|---|
| Crítica | Bus Digital / TopPeru | Venta y reserva de pasajes, rutas, horarios, asientos, encomiendas, caja, liquidaciones y comprobantes. | Interrupción de ventas; inconsistencias de asientos/pagos; exposición de datos de pasajeros. | Funciones y arquitectura lógica conocidas por código y presentaciones; despliegue productivo no confirmado. |
| Crítica | Base de datos relacional MySQL/MariaDB | Persistencia del sistema core y transacciones. | Disponibilidad, integridad y confidencialidad del activo central. | Tecnología compatible conocida; versión, topología, cuenta SQL y controles productivos pendientes. |
| Crítica | Facturación electrónica / SUNAT, mencionándose Greenter | Emisión y envío de comprobantes. | Riesgo tributario, operativo y de conciliación. | Integración identificada; contrato, credenciales, SLA y contingencia pendientes. |
| Alta | Pasarelas/procesadores de pago | Validación y registro de pagos. | Fraude, venta no conciliada o indisponibilidad. | Dependencia funcional conocida; proveedores y contratos vigentes pendientes. |
| Alta | Hosting/VPS, DNS, CDN, certificados TLS y servidor web | Publicación y disponibilidad de aplicaciones. | Caída o exposición externa del servicio. | Existencia genérica declarada; proveedor, inventario y configuración reales pendientes. |
| Alta | Repositorios y cadena de desarrollo/despliegue | Código, cambios, migraciones y entregas. | Alteración de software, secretos o producción. | Git y migraciones observados localmente; plataforma, MFA, permisos, revisiones y CI/CD pendientes. |
| Alta | Correo corporativo y mensajería | Comunicación interna, comercial y recuperación de cuentas. | Phishing, fraude y toma de cuentas. | Se mencionan Mailjet, Brevo, WhatsApp/Pusher en código; correo corporativo y controles reales pendientes. |
| Alta | Backups y recuperación | Continuidad tras falla o ransomware. | Pérdida prolongada de operación y datos. | No existe evidencia productiva suficiente en los informes previos. |
| Media/alta | RENIEC y RedBus | Identidad e intercambio/venta de pasajes. | Fallas externas y tratamiento de datos. | Integraciones identificadas; alcance, contrato y SLA pendientes. |
| Media/alta | Equipos, red, Wi-Fi, firewall y acceso remoto de la sede | Operación del personal y administración. | Entrada inicial, movimiento lateral o fuga. | Sin inventario corporativo validado ni diagrama vigente. |
| Por confirmar | Activos de la agencia Arequipa del inventario F-07 | Puestos y periféricos de atención. | Continuidad y posible exposición en punto de venta. | No se ha demostrado que pertenezcan o sean administrados por AM Digital. |

### 4.2 Terceros y relaciones a confirmar

Las fuentes mencionan Google Cloud Platform/Google Partner Ecosystem, RedBus, RENIEC, SUNAT/Greenter, pasarelas de pago, Pusher, Mailjet, Brevo, WhatsApp, proveedores de hosting/VPS, DNS/CDN y certificados (incluido Let’s Encrypt), además de clientes de transporte. Ninguna mención acredita por sí sola un contrato vigente, tratamiento de datos, acceso administrativo, subencargados, SLA, derecho de auditoría, notificación de incidentes o cláusulas de seguridad.

Se debe construir con TI y gerencia un registro único que identifique por tercero: servicio, dueño interno, datos tratados, acceso lógico/físico, cuentas, ambientes, dependencia crítica, contrato/SLA, cláusulas de confidencialidad y seguridad, fecha de evaluación y plan de salida.

### 4.3 Dependencias y puntos de concentración preliminares

- La venta depende de disponibilidad, base de datos, pagos, facturación y conectividad; una falla externa puede dejar estados incongruentes.
- El informe anterior plantea como hipótesis —no confirmada— aplicación y BD en un solo host, lo que podría constituir un punto único de falla.
- La restauración solo de la BD podría dejar fuera archivos operativos y cargas; además, correlativos y colas de SUNAT podrían quedar desalineados.
- La baja de usuarios observada en código no mostró revocación integral de sesiones/tokens; debe verificarse en el servicio vigente y con RR. HH.
- Los logs y herramientas de diagnóstico podrían contener cabeceras, cuerpos, tokens o datos personales; el comportamiento productivo está pendiente.
- Las migraciones históricas editadas y reversiones potencialmente destructivas son antecedentes relevantes para cambios y recuperación, no un hallazgo de ciberseguridad confirmado.

## 5. Evidencias reutilizables del Taller 02

| Tema T03 | Evidencia heredada útil | Uso permitido en esta etapa | Validación posterior necesaria |
|---|---|---|---|
| Activos y arquitectura | Arquitectura lógica Laravel 10/Blade-Livewire/Eloquent; conexión compatible con MySQL/MariaDB; APIs, colas y Scheduler. | Preparar entrevistas y mapa lógico. | Inventario y diagrama productivo aprobados por TI. |
| Identidades y accesos | Fortify, Jetstream, Sanctum y Spatie Permission; roles funcionales; indicio de rutas con autorización desigual y baja incompleta. | Definir muestras y preguntas PR-01 a PR-04. | Configuración mostrada por TI y evidencia de proceso RR. HH.–TI. |
| Protección de datos | El modelo contempla datos identificativos, contacto, nacimiento, domicilio, viajes, pagos y menores. | Confirmar criticidad y requisitos legales. | Registro de bancos de datos, flujos, clasificación, retención y responsables. |
| Logs/detección | Logs diarios, Telescope, middleware API, Laravel Auditing e historiales; ejemplo local de trazabilidad. | Inventariar fuentes candidatas de logs. | Consolas, retención, alertas, responsables y evidencias productivas. |
| Parches/plataforma | Laravel 10.48.28 observado y señalado como fuera de soporte; versiones locales no equivalen a producción. | Priorizar inventario y ciclo de vida. | Versiones productivas y plan de parches. |
| Backups/recuperación | Ausencia de evidencia en el repositorio; riesgo de recuperar BD sin archivos, colas y correlativos. | Preparar solicitud RC-01 a RC-03. | Política, jobs, reportes, copia inmutable/offline y actas de restauración. |
| Cambios | Git y migraciones; ausencia de evidencia de aprobación/CI-CD; migraciones editadas. | Preparar solicitud de SDLC y trazabilidad. | Procedimiento, aprobaciones, segregación y muestra de cambios reales. |
| Continuidad/terceros | Integraciones y dependencias identificadas; RPO/RTO, HA y SLA no acreditados. | Elaborar mapa de dependencias. | BIA, contratos, RTO/RPO, arquitectura y ejercicios. |

## 6. Matriz base de los 46 controles

**Leyenda:** “Conocido” describe únicamente lo que ya consta; no equivale a cumplimiento. Todo control permanece **sin evaluar** hasta obtener evidencia suficiente de existencia formal y operación efectiva.

| ID | Conocido / evidencia reutilizable | Pendiente para evaluar existencia y operación | Fuente base |
|---|---|---|---|
| GV-01 | La presentación corporativa afirma políticas de calidad, antisoborno y privacidad. | PSI/ciberseguridad vigente, aprobación de alta dirección, versión, fecha y difusión. | F-05 |
| GV-02 | Se reconocen Gerencia/CEO y Dirección de Tecnología; no un responsable formal de seguridad. | Organigrama, designación, dependencia, funciones, suplencia y posible conflicto con TI. | F-05 |
| GV-03 | No hay matriz ni metodología corporativa disponible. Los informes anteriores solo listan riesgos preliminares. | Metodología, apetito/tolerancia, matriz vigente, responsables y seguimiento. | F-03 |
| GV-04 | Bus Digital trata datos personales y se relaciona con pagos/facturación. La guía identifica Ley 29733, reglamento y Ley 30096. | Inventario legal/contractual, registro de bancos de datos, responsable y evaluación sectorial por cliente. | F-01, F-03 |
| GV-05 | No existe evidencia reutilizable de presupuesto de ciberseguridad. | Confirmación de gerencia, planificación y asignación, sin exigir montos confidenciales. | — |
| GV-06 | Hay una lista preliminar de proveedores/integraciones. | Registro vigente, accesos, contratos, cláusulas, SLA, evaluaciones, subencargados y salida. | F-03, F-05, F-06 |
| GV-07 | No existe evidencia de informes periódicos a gerencia. | Actas, tablero, periodicidad, destinatarios y decisiones tomadas. | — |
| ID-01 | Existe un inventario de una agencia Arequipa con 44 impresoras híbridas, 33 pin pads y 56 lectoras; incluye estaciones, duplicados aparentes y activos sin estación. | Propietario, alcance, fecha, responsable, conciliación física; inventario completo de AM Digital: servidores, PCs, móviles, red, IoT y nube. | F-07 |
| ID-02 | El repositorio permite identificar dependencias de software; no equivale a inventario instalado/licenciado. | Inventario de software/SaaS/licencias, versiones, dueños, equipos y control de shadow IT. | F-03 |
| ID-03 | Se conocen categorías de datos personales y operativos en Bus Digital. | Política de clasificación, propietarios, ubicaciones, flujos, retención y etiquetado. | F-03 |
| ID-04 | Se declaran web, APIs, hosting/VPS, DNS/CDN, TLS y servicios externos; no se confirmó exposición real. | Relación declarada y aprobada por TI de servicios expuestos, dueño, ambiente y propósito. Sin escaneo. | F-03, F-06 |
| ID-05 | No existe informe de análisis de vulnerabilidades reutilizable. | Último resumen, alcance, fecha, proveedor, plan y cierre de hallazgos. | — |
| ID-06 | F-03 menciona un “documento de pentest” como fuente secundaria, sin incorporarlo como evidencia suficiente. | Confirmar prueba, autorización, alcance, fecha, resumen ejecutivo y remediación. | F-03 |
| ID-07 | El proceso core y dependencias están descritos; no hay BIA. | BIA aprobado, procesos críticos, MTPD, RTO/RPO, dueños y dependencias. | F-06 |
| PR-01 | El código admite 2FA mediante Fortify/Jetstream. | Configuración y cobertura efectiva de MFA en correo, nube, repositorio, VPN y cuentas administrativas. | F-03 |
| PR-02 | Hay roles funcionales en la aplicación; cuentas y privilegios SQL/productivos no fueron verificados. | Listas enmascaradas de administradores locales, dominio, servidores, nube, BD y firewall; justificación y revisión. | F-03 |
| PR-03 | Indicio de desactivación incompleta en código; el Taller 02 no hizo cruce con cesados. | Procedimiento RR. HH.–TI y muestra reciente, anonimizada, de alta/cambio/baja con revocación de sesiones/tokens. | F-03 |
| PR-04 | Se identifican cuentas de aplicación/servicio; no se conoce si existen cuentas humanas genéricas o compartidas. | Inventario enmascarado, propósito, custodio, autenticación y plan de eliminación/compensación. | F-03 |
| PR-05 | No hay plan ni registros corporativos de concientización disponibles. | Programa anual, contenidos, asistencia, cobertura de gerencia y métricas. | — |
| PR-06 | No hay evidencia de simulaciones de phishing. | Confirmar si se realizaron y solicitar resumen autorizado; no ejecutar una simulación en este taller. | — |
| PR-07 | Laravel 10.48.28 fue observado y reportado fuera de soporte; producción no se confirmó. | Inventario de versiones, EOL, política, calendario, excepciones y muestra mostrada por TI. | F-03 |
| PR-08 | No hay evidencia de antimalware/EDR corporativo. | Consola mostrada, cobertura por tipo de activo, equipos sin agente y atención de alertas. | — |
| PR-09 | No hay evidencia sobre credenciales por defecto ni hardening. | Guías/baselines y demostración por TI sin revelar contraseñas. | — |
| PR-10 | No hay evidencia sobre cifrado de laptops, USB o DLP. El LUKS de una estación del investigador no es evidencia corporativa. | Política y consola/configuración mostrada; excepciones, custodia de claves y dispositivos personales. | F-03 |
| PR-11 | No hay observación física realizada. | Recorrido autorizado: acceso, registro, UPS, extintor, temperatura y protección del rack/cuarto. | F-01 |
| PR-12 | No hay diagrama ni evidencia de VLAN corporativa validada. | Diagrama sin IP sensibles y configuración mostrada de segmentación de usuarios, servidores, invitados e IoT. | — |
| PR-13 | La existencia/configuración del firewall no está acreditada. | Responsable, plataforma, revisión de reglas, excepciones y registro de última revisión. | — |
| PR-14 | El acceso de desarrolladores a producción aparece solo como fuente secundaria; VPN/RDP/herramientas remotas no confirmados. | Matriz de accesos remotos, MFA, aprobaciones, registros y herramientas autorizadas. | F-03 |
| PR-15 | No hay evidencia de configuración Wi-Fi. | WPA2/WPA3, redes, aislamiento de invitados, rotación de credenciales y baja de ex trabajadores. | — |
| PR-16 | Se usan servicios de correo/mensajería, pero no hay evidencia de filtro ni SPF/DKIM/DMARC. | Configuración mostrada o reportes del proveedor. Una consulta DNS pública requerirá autorización de actividad para una etapa posterior. | F-03 |
| DE-01 | El código contempla logs diarios, Telescope, auditoría e historiales; la instancia local mostró cobertura heterogénea. | Fuentes productivas, centralización, integridad, accesos, retención, rotación y reloj. | F-03, F-04 |
| DE-02 | No hay evidencia de SIEM/SOC. | Contrato o arquitectura, cobertura, horarios, SLA y consola mostrada. | — |
| DE-03 | Hay fuentes potenciales de alertas, pero no responsables ni casos atendidos. | Matriz de alertamiento, destinatarios, guardias, escalamiento y muestra anonimizada. | F-03 |
| DE-04 | No se acreditaron reglas de accesos anómalos. | Reglas, umbrales, cobertura, pruebas documentadas y ejemplos anonimizados. | — |
| DE-05 | No hay registro corporativo de incidentes disponible. | Registro de 12 meses, método de detección, MTTD y lecciones, anonimizado. | — |
| RS-01 | No se localizó un plan en el repositorio; esto no prueba inexistencia corporativa. | Plan aprobado, roles, severidad, escalamiento, contactos y copias fuera de línea. | F-03 |
| RS-02 | No se conoce canal ni conocimiento del personal. | Procedimiento/canal y resultado de encuesta autorizada a mínimo 15 trabajadores. | F-01 |
| RS-03 | No hay registro reutilizable de incidentes corporativos. | Registro anonimizado de 12 meses, clasificación, responsables y cierre. | — |
| RS-04 | No se ha realizado entrevista ni ejercicio sobre ransomware. | Respuestas separadas de jefe de TI y gerencia; autoridad para aislar, comunicar, continuidad y decisión sobre rescate. | F-01 |
| RS-05 | Se reconoce aplicabilidad potencial de protección de datos; no hay procedimiento de notificación. | Procedimiento legal vigente, roles, evaluación de afectación, plazos y contactos. | F-01, F-03 |
| RS-06 | No hay actas de tabletop/simulacros. | Acta, escenario, participantes, resultados y acciones de mejora. | — |
| RC-01 | No se encontró plan de recuperación en el repositorio; una recuperación solo de BD sería insuficiente. | DRP ante ciberataque, orden de recuperación, dependencias, responsables y copia accesible durante crisis. | F-03 |
| RC-02 | No hay evidencia productiva de copia offline/inmutable, credenciales separadas ni regla 3-2-1-1-0. | Arquitectura y consola mostrada, cuentas, inmutabilidad, cifrado, retención y monitoreo. | F-03 |
| RC-03 | No hay acta de recuperación completa. La prueba local de ROLLBACK no es una restauración. | Última prueba integral, alcance, tiempos, RTO/RPO, validaciones y acciones correctivas. | F-03, F-04 |
| RC-04 | No hay plan de comunicación postincidente. | Audiencias, responsables, plantillas, canales alternos y coordinación legal/comercial. | — |
| RC-05 | No hay informes postincidente disponibles. | Muestra anonimizada de lecciones, responsables, plazos y verificación de mejoras. | — |

### Resumen de preparación de controles

- **46/46 controles:** identificados y mapeados.
- **0/46 controles:** evaluados en esta etapa.
- **46/46 controles:** conservan al menos una necesidad de confirmación o evidencia operativa.
- La mayor reutilización documental se concentra en ID, PR, DE y RC; GV, RS, seguridad física y factores humanos tienen los vacíos más amplios.

## 7. Actividades que requieren autorización complementaria

La autorización descrita en el Taller 02 está limitada a consultas `SELECT` supervisadas. Antes de cualquiera de las actividades siguientes se requiere una **adenda o nueva autorización escrita** firmada por gerencia o responsable competente, con fechas, sedes, responsables, tratamiento de datos y reglas de confidencialidad.

| Actividad | Autorización y condiciones mínimas | Datos / salvaguardas | Estado |
|---|---|---|---|
| Entrevistas | Autorizar entrevistas por cargo a gerencia, TI/tecnología, RR. HH. y, si corresponde, comercial/operaciones. Definir agenda, duración, registro de notas y validación de acta. | No solicitar contraseñas ni secretos. Identificar por cargo en el informe. Grabación solo con consentimiento separado. | REQUERIDA |
| Encuesta a mínimo 15 trabajadores | Aprobación de gerencia y RR. HH.; invitación voluntaria, anónima, multiarea y sin represalias; definir quién distribuye y recibe. | No recolectar nombre, correo, DNI, IP ni respuesta individual atribuible. Reportar agregados; suprimir cruces de áreas con muy pocos participantes. | REQUERIDA |
| Recorrido físico | Autorizar fecha, zonas, acompañante y límites; incluir sede, puestos, recepción y rack/cuarto técnico solo si corresponde. | Sin fotos de personas o pantallas. Fotos de infraestructura únicamente con permiso explícito; notas sin IP, usuarios o secretos. No conectar equipos ni manipular dispositivos. | REQUERIDA |
| Visualización de configuraciones | Autorizar observación de solo lectura, dirigida y ejecutada por TI: correo/MFA, EDR, firewall, VPN, Wi-Fi, backups, logs/SIEM, nube, repositorio y accesos. Definir sistemas, pantallas, horario y acompañante. | TI navega; el auditor no opera. Enmascarar secretos, IP públicas, datos personales y tokens. Capturas solo si están expresamente autorizadas; sin cambios ni comandos. | REQUERIDA |

La autorización debe aclarar además si se permite revisar configuraciones y evidencias de **clientes de AM Digital**. Sin consentimiento del cliente/propietario, esas instalaciones se excluyen.

## 8. Solicitud priorizada de evidencias

### 8.1 Al jefe de TI / Dirección de Tecnología

**Prioridad 1 — bloqueantes para alcance y riesgos críticos**

1. Inventario vigente de activos de AM Digital y activos administrados para Bus Digital, con propietario, ubicación/entorno, responsable, criticidad, versión y soporte; separar claramente activos propios y de clientes.
2. Diagramas lógico y físico vigentes, incluyendo nube/hosting, red, firewall, VPN/acceso remoto, ambientes, BD, almacenamiento, DNS/CDN y flujos con terceros; entregar versión sanitizada.
3. Relación declarada de servicios expuestos a Internet y accesos administrativos/remotos, sin realizar escaneo: servicio, dueño, ambiente, propósito, método de acceso y MFA.
4. Arquitectura y evidencia de backups: jobs, frecuencia, retención, cifrado, ubicaciones, copia offline/inmutable, cuentas/custodios, reportes de ejecución y última prueba de restauración integral.
5. RPO/RTO aprobados y DRP/BCP aplicable a Bus Digital; última prueba, tiempo real obtenido y acciones pendientes.
6. Matriz de identidades y privilegios enmascarada para correo, nube, repositorios, servidores, BD, firewall, VPN y Bus Digital; incluir cuentas privilegiadas, genéricas, servicio y terceros.
7. Evidencia del proceso de baja integral: desactivación, sesiones, tokens, VPN, correo, repositorio, nube y credenciales compartidas; muestra anonimizada de 2–3 ceses recientes coordinada con RR. HH.
8. Configuración mostrada de MFA y cobertura en correo, nube, repositorios, VPN y cuentas administrativas.

**Prioridad 2 — protección y detección**

9. Inventario de software/SaaS/licencias y reporte de versiones/EOL; política, calendario, excepciones e historial reciente de parches.
10. Evidencia de EDR/antimalware: cobertura, consola, políticas, equipos sin agente y ejemplo anonimizado de alerta atendida.
11. Diagrama de segmentación y redes Wi-Fi; separación de servidores, personal, invitados e IoT; responsable y revisión de firewall.
12. Registro de herramientas de acceso remoto (VPN, RDP, AnyDesk, TeamViewer u otras), autorizaciones, MFA y trazabilidad.
13. Inventario de fuentes de logs; política de retención/rotación; centralización/SIEM/SOC; reglas y alertas; responsables y guardias.
14. Configuración de correo: antispam/antiphishing y reportes del proveedor sobre SPF, DKIM y DMARC.
15. Baselines de hardening, control de contraseñas predeterminadas, cifrado de laptops, USB/BYOD y medidas DLP.
16. Procedimiento de gestión de cambios y SDLC seguro; repositorio, ramas, revisiones, secretos, CI/CD, segregación de ambientes, aprobaciones y muestra de cambios.
17. Último resumen de análisis de vulnerabilidades/pentest y plan de remediación, si existen. No se solicita ejecutar uno nuevo.

**Prioridad 3 — soporte documental**

18. Procedimientos técnicos de operación, alta/baja, backup, restauración, monitoreo, incidentes y recuperación con versión, autor y aprobación.
19. Registro de incidentes de los últimos 12 meses, anonimizado, con origen, detección, tiempos, impacto, respuesta y lecciones.
20. Relación técnica de proveedores con acceso, cuentas, responsables, SLA y dependencias; incluir hosting, nube, pagos, SUNAT/Greenter, RENIEC, RedBus, correo/mensajería y soporte.

### 8.2 A gerencia

**Prioridad 1**

1. Nueva autorización escrita del Taller 03 y anexos específicos para entrevistas, encuesta, recorrido y visualización de configuraciones.
2. Confirmación del alcance: AM Digital, Bus Digital, sede(s), servicios administrados y exclusión/inclusión de ambientes de clientes.
3. Organigrama vigente y designaciones de responsables de TI, seguridad, continuidad, incidentes, protección de datos y relación con terceros.
4. Política de Seguridad de la Información/ciberseguridad y políticas relacionadas, con aprobación, fecha, versión y difusión.
5. Matriz/metodología de riesgos, apetito o tolerancia, responsables y tratamiento.
6. BIA y prioridades del negocio: procesos críticos, impacto, dependencias, MTPD, RTO y RPO.

**Prioridad 2**

7. Inventario de requisitos legales, regulatorios y contractuales; registro de bancos de datos personales y responsable legal.
8. Registro de proveedores críticos, contratos y anexos de seguridad/confidencialidad, SLA, notificación de incidentes, derecho de auditoría y salida.
9. Evidencia de presupuesto/plan de ciberseguridad; puede limitarse a existencia, responsables y líneas aprobadas, sin revelar montos.
10. Informes, actas o indicadores de ciberseguridad presentados a gerencia y decisiones derivadas.
11. Plan de respuesta a incidentes, crisis y comunicación, incluidos contactos alternos y escenario ransomware.
12. Actas de simulacros/tabletop y reportes postincidente con acciones de mejora.

### 8.3 A RR. HH.

**Prioridad 1**

1. Autorización y coordinación de la encuesta anónima a mínimo 15 trabajadores de distintas áreas; confirmar población, áreas y mecanismo que preserve anonimato.
2. Procedimiento de altas, cambios y ceses que active acciones de TI, con SLA, responsables y evidencia de notificación.
3. Relación anonimizada de ceses/traslados recientes para seleccionar, junto con TI, una muestra de 2–3 casos; no entregar datos personales innecesarios.
4. Organigrama, perfiles y funciones de puestos con responsabilidades de seguridad, TI, DBA, soporte, continuidad y privacidad.

**Prioridad 2**

5. Plan y registros de capacitación/concientización de los últimos 12 meses, incluidos gerencia, personal nuevo y contratistas.
6. Evidencia de entrega/aceptación de políticas, reglamentos, confidencialidad, uso aceptable, BYOD y trabajo remoto.
7. Procedimiento disciplinario y canal de reporte de incidentes o correos sospechosos, sin casos personales identificables.
8. Cláusulas de confidencialidad y seguridad aplicables a trabajadores y terceros, en formato modelo o anonimizado.

## 9. Criterios de aceptación y custodia de evidencia

- Cada evidencia debe registrar: código, título, propietario, fecha, versión, ambiente, fuente, responsable que la mostró y controles relacionados.
- Preferir copias sanitizadas, extractos, reportes o capturas enmascaradas; no recolectar secretos ni bases de datos.
- Separar evidencia de AM Digital, evidencia de cliente e información del laboratorio/local.
- Para demostrar operación, solicitar una muestra fechada y trazable; una política sola demuestra formalización, no funcionamiento.
- Para demostrar formalización, exigir aprobación, vigencia, propietario y difusión; una entrevista sola no demuestra que el control esté escrito.
- Conservar las evidencias en repositorio restringido, con nombres neutros, acceso mínimo y canal de entrega acordado.
- El inventario F-07 no debe anexarse íntegro a una versión ampliamente compartida porque contiene identificadores de activos.

## 10. Secuencia recomendada después de la autorización

1. Gerencia confirma alcance, sedes, clientes excluidos/incluidos y responsables.
2. TI entrega inventarios, diagramas, mapa de exposición declarado y evidencia crítica de backup/identidades.
3. RR. HH. y TI preparan la muestra de altas/bajas y la encuesta anónima.
4. Se realizan entrevistas por cargo y se levantan actas.
5. TI muestra configuraciones de solo lectura y enmascaradas.
6. Se ejecutan encuesta y recorrido bajo las condiciones autorizadas.
7. Recién entonces se evalúan los 46 controles, distinguiendo existencia formal y operación efectiva, y se construyen perfil de madurez, hallazgos y plan de tratamiento.

## 11. Pendientes y decisiones de apertura

- Confirmar que la empresa auditada del Taller 03 es AM Digital Web E.I.R.L. y que Bus Digital es el sistema crítico principal.
- Determinar si TopPeru es producto base, una instalación de cliente o ambas cosas.
- Determinar qué infraestructura administra AM Digital y cuál pertenece a transportistas/clientes.
- Confirmar la relación y vigencia del inventario de la agencia Arequipa; los dos archivos disponibles parecen copias del mismo documento.
- Identificar al jefe de TI/Director de Tecnología, enlace de gerencia y enlace de RR. HH. que validarán evidencias.
- Obtener la autorización complementaria antes de cualquier actividad de campo o visualización.
- Mantener suspendida toda verificación activa y todo control posterior hasta que el alcance y la autorización queden formalizados.

---

**Estado de la ETAPA 0:** preparación documental completada con reservas. La matriz está lista para levantamiento de evidencia, pero ningún control ha sido declarado conforme, no conforme ni maduro.
