# Sistema Visual INFOMATT

## Objetivo
Aplicar la linea grafica aprobada al frontend de InfoMatt360, manteniendo consistencia visual en Web, Runtime, Builder, Android y Desktop.

## Paleta aprobada

```text
Azul oscuro:   #0A2540
Azul principal:#0066CC
Cian:          #00C2FF
Azul claro:    #E6F1FA
Blanco:        #FFFFFF
```

## Tipografia

```text
Montserrat
```

Uso previsto:

- titulos en SemiBold o Bold;
- textos operativos en Regular;
- botones y estados en Bold.

## Linea grafica

- interfaz enterprise limpia;
- sidebar oscuro con acento cian;
- tarjetas blancas con sombra suave;
- botones en gradiente azul-cian;
- iconografia lineal, moderna y redondeada;
- alto contraste para entornos operativos.

## Archivos agregados

```text
frontend/src/theme/brand.ts
frontend/src/components/BrandLogo.tsx
frontend/src/components/AppShell.tsx
```

## Archivos actualizados

```text
frontend/src/modules/runtime/RuntimeApp.tsx
frontend/src/styles.css
```

## Decision tecnica
El Runtime Renderer usa AppShell desde el inicio para que el MVP no parezca una demo aislada, sino parte de una plataforma operacional.

## Pendientes

- integrar iconos SVG propios;
- crear biblioteca de botones y tarjetas;
- adaptar Builder Visual a la misma linea;
- crear pantalla dashboard base;
- crear login con marca INFOMATT.
