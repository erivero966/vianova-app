# Protocolo de pruebas de usuario: usabilidad y accesibilidad

**Proyecto:** Aplicación móvil Vianova · **Normas de referencia:** ISO 9241-11:2018 (efectividad, eficiencia, satisfacción),
ISO 9241-210:2019 (diseño centrado en el usuario), WCAG 2.1 nivel AA (accesibilidad) · **Requerimientos:** RNF-U01, RNF-ST01, RNF-PT01

> **Estado:** protocolo e instrumentos listos. Los resultados se registran en `resultados_participantes.csv` y
> `sus_respuestas.csv` después de cada sesión, y se procesan con `python analizar_usuarios.py`.
> **No se deben inventar ni completar resultados sin haber realizado las sesiones.**

## 1. Objetivo
Verificar que cuidadores familiares puedan completar las tareas críticas de la app sin ayuda, con pocos errores y en
poco tiempo, y obtener su percepción de usabilidad (SUS) y sus observaciones sobre la interfaz y la accesibilidad.

## 2. Participantes (grupo designado de retroalimentación)
| Grupo | N.º | Perfil | Propósito |
|---|---|---|---|
| G1 · Cuidadores familiares | 5 a 8 | Cuidan a un familiar con cáncer; usan celular Android o iPhone | Usabilidad de las tareas críticas |
| G2 · Usuarios con necesidades de accesibilidad | 2 a 3 | Adultos mayores, baja visión o poca experiencia digital | Accesibilidad (zoom, lector de pantalla, tamaño de letra) |
| G3 · Expertos | 2 | Profesional de salud (enfermería oncológica) e ingeniero de sistemas/UX | Evaluación heurística y pertinencia del contenido |

Cinco participantes por perfil permiten detectar la mayor parte de los problemas de usabilidad (Nielsen y Landauer, 1993).
La selección es por conveniencia, con consentimiento informado firmado.

## 3. Seguridad de la información durante las pruebas
- Las sesiones se hacen en el **ambiente de PRUEBAS** (`APP_ENV=pruebas`), que muestra la franja «solo datos ficticios».
- Los participantes **no ingresan datos reales** de su familiar: usan el **caso ficticio** de la sección 5 y una cuenta
  de prueba creada para la sesión (`participanteNN@ficticio.pe`).
- Los formularios en papel o digitales identifican al participante solo con un código (P01, P02…). La lista que
  vincula código y nombre la guarda el responsable del estudio, separada de los resultados.
- Las grabaciones de pantalla (si se autorizan) se guardan en el almacenamiento institucional en la nube y se borran
  al terminar el análisis. **Nunca se copian a discos externos ni a memorias USB.**
- Al terminar la ronda se borra la base del ambiente de pruebas.

## 4. Procedimiento (30 a 40 minutos por participante)
1. Bienvenida, explicación y firma del consentimiento (5 min).
2. Cuestionario de perfil: edad, parentesco, experiencia con apps y tipo de celular (3 min).
3. Tareas con la técnica de «pensar en voz alta». El moderador no ayuda salvo que pasen 3 minutos sin avance; en ese caso la tarea se marca como «con ayuda» (20 min).
4. Cuestionario SUS (10 ítems, escala de 1 a 5) (3 min).
5. Entrevista breve: qué fue lo más difícil, qué cambiaría y si usaría la app (5 min).
6. G2: lista de verificación de accesibilidad con el celular del participante (zoom de 200 %, TalkBack/VoiceOver, modo oscuro y letra grande del sistema).

## 5. Caso ficticio para las tareas
> «Usted cuida a su papá, Jorge, de 68 años, que tiene cáncer de colon y recibe quimioterapia. Se moviliza con ayuda.
> El oncólogo le indicó un medicamento para las náuseas cada 8 horas desde las 8:00 a. m. y tiene control el próximo
> viernes a las 10:00 a. m.»

## 6. Tareas críticas y criterios de éxito
| ID | Tarea | RF | Criterio de éxito | Tiempo objetivo |
|---|---|---|---|---|
| T1 | Crear una cuenta aceptando el consentimiento y completar el perfil de Jorge | RF-01 | Perfil guardado con tipo de cáncer y tratamiento | ≤ 3 min |
| T2 | Registrar el medicamento cada 8 horas y la cita del viernes | RF-02 | Ambas tareas aparecen en la agenda | ≤ 3 min |
| T3 | Marcar como hecha la toma de las 8:00 | RF-02, RF-03 | Estado «Hecha» | ≤ 30 s |
| T4 | Registrar por voz o texto: «anoche tuvo fiebre de 38,5» y confirmarlo | RF-04, RF-09 | Registro guardado y aviso leído | ≤ 1,5 min |
| T5 | Preguntar qué puede comer si tiene llagas en la boca y decir de qué guía sale la respuesta | RF-06, RF-07 | Lee la fuente correctamente | ≤ 1,5 min |
| T6 | Buscar una recomendación sobre cansancio y valorarla | RF-05, RF-08 | Valoración registrada | ≤ 1 min |
| T7 | Descargar el resumen para llevar al control | RF-10 | Archivo descargado o vista de impresión | ≤ 1 min |
| T8 | Revocar la autorización de dispositivos o descargar sus datos | RF-15 | Acción completada | ≤ 1,5 min |

**Métricas por tarea:** éxito (1 = sin ayuda, 0,5 = con ayuda, 0 = no completada), tiempo en segundos, número de
errores (acciones que no llevan a la meta) y observaciones.

**Criterios de aceptación (RNF-U01):** al menos 80 % de los participantes completa las tareas críticas sin ayuda;
SUS promedio ≥ 68 (por encima del promedio de referencia; Bangor et al., 2009); ninguna barrera de accesibilidad crítica sin plan de corrección.

## 7. Cuestionario SUS (adaptado al español)
Escala: 1 = totalmente en desacuerdo … 5 = totalmente de acuerdo.
1. Creo que me gustaría usar esta aplicación con frecuencia.
2. Encontré la aplicación innecesariamente complicada.
3. Pensé que la aplicación era fácil de usar.
4. Creo que necesitaría ayuda de una persona con conocimientos técnicos para usar esta aplicación.
5. Las funciones de la aplicación están bien integradas.
6. Pensé que había demasiada inconsistencia en la aplicación.
7. Imagino que la mayoría de las personas aprendería a usar esta aplicación muy rápidamente.
8. Encontré la aplicación muy difícil de usar.
9. Me sentí muy seguro(a) usando la aplicación.
10. Necesité aprender muchas cosas antes de poder usar la aplicación.

Puntaje: ítems impares (respuesta − 1); ítems pares (5 − respuesta); suma × 2,5 (0 a 100).

## 8. Lista de verificación de accesibilidad (G2 y experto)
| ID | Criterio (WCAG 2.1) | Cómo se verifica |
|---|---|---|
| A1 | 1.4.4 Cambio de tamaño del texto | Zoom del navegador al 200 %: el contenido sigue legible y sin cortes |
| A2 | 1.4.10 Reajuste (reflow) | Sin desplazamiento horizontal a 320 px de ancho |
| A3 | 1.4.3 Contraste mínimo | Texto legible a pleno sol; verificación automática con axe-core |
| A4 | 2.5.5 Tamaño del objetivo táctil | Botones de al menos 44 × 44 px; se pulsan sin errores |
| A5 | 4.1.2 Nombre, función y valor | TalkBack/VoiceOver lee correctamente botones, campos y pestañas |
| A6 | 2.4.1 Evitar bloques | El enlace «Saltar al contenido» funciona con teclado |
| A7 | 3.3.1 / 3.3.2 Errores y etiquetas | Los mensajes de error indican qué corregir; todos los campos tienen etiqueta |
| A8 | 1.1.1 Contenido no textual | Íconos decorativos ocultos al lector; el micrófono tiene texto |

## 9. Levantamiento de observaciones
Cada problema detectado se registra en `../registro_observaciones.csv` con su severidad (Nielsen, de 0 a 4), el RF o
RNF afectado, la acción correctiva, el responsable y el estado. Una observación se cierra solo cuando la corrección
se verifica: con la prueba automatizada correspondiente o repitiendo la tarea con otro participante.
