# Diseño: Material 3 simple

Referencias exactas en `docs/diseno/` (01 lista, 02 elegir carpeta,
03 confirmar datos, 04 proyecto agregado).

## Tokens (`src/styles.css`)

| Variable | Valor | Uso |
|---|---|---|
| `--bg` | `#F4F3FA` | Fondo de la app |
| `--surface` | `#FFFFFF` | Contenedor de la lista |
| `--surface-high` | `#ECEAF4` | Diálogos |
| `--on-surface` | `#1B1B21` | Texto principal |
| `--on-surface-variant` | `#45464F` | Texto secundario |
| `--outline` | `#767680` | Bordes de campos y botones con contorno |
| `--outline-variant` | `#E4E1EC` | Divisores |
| `--primary` | `#3F51B5` | Botón principal, foco |
| `--primary-container` | `#DFE0FF` | Botón tonal, chip "Escaneando" |
| `--on-primary-container` | `#0E1A63` | Texto sobre lo anterior |
| `--pass-bg` / `--pass-fg` | `#D3F0DC` / `#0F5130` | Chip Aprobado |
| `--fail-bg` / `--fail-fg` | `#FFDAD6` / `#8C1D18` | Chip No aprobado |
| `--inverse-surface` | `#303036` | Snackbar |

Tipografía: Roboto Flex (o la del sistema). Título de pantalla 28/36 peso 500;
nombre de proyecto 16/24 peso 500; texto de apoyo 14/20; chips 13 peso 500.

## Componentes

- **Fila de proyecto** (lista de dos líneas, mínimo 72 px): nombre + chip en
  la primera línea, "Último escaneo: 6 nov 2026, 10:42" debajo, botón a la derecha.
  Filas separadas por divisor de 1 px dentro de una superficie con radio 16.
- **Chip de estado** (radio 8, alto 28): Aprobado (check), No aprobado (X),
  Sin análisis (contorno), Escaneando (tonal). Nunca solo color: siempre ícono o contorno.
- **Botón Escanear**: tonal, píldora de 40 px, ícono play.
- **Escaneando**: chip "Escaneando", texto "Compilando, paso 2 de 3",
  indicador circular + botón "Cancelar" con contorno, barra lineal de 4 px
  en el borde inferior de la fila.
- **Cabecera**: título "Proyectos", indicador de SonarQube, botón con contorno
  "Agregar" y botón relleno "Escanear todos".
- **Diálogo** (radio 28, máx. 560 px, scrim 32 %): campos con contorno de 56 px
  y etiqueta flotante, botón segmentado para la capa, casillas, acciones a la derecha.
- **Snackbar**: abajo al centro, superficie inversa, texto + cerrar.

Accesibilidad: botones reales, foco visible, `aria-label` en botones de solo ícono,
contraste 4.5:1.
