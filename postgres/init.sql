-- ══════════════════════════════════════════════════════
-- AUTH + AUDITORÍA (mcp-fintech)
-- ══════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS api_consumers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre          VARCHAR(100) NOT NULL,
    api_key         VARCHAR(100) NOT NULL UNIQUE,
    rol             VARCHAR(20)  NOT NULL CHECK (rol IN ('user', 'admin')),
    permisos        JSONB        NOT NULL DEFAULT '[]',
    rate_limit_hora INT          NOT NULL DEFAULT 100,
    activo          BOOLEAN      NOT NULL DEFAULT true,
    creado_en       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consumer_id UUID        NOT NULL REFERENCES api_consumers(id),
    mcp_server  VARCHAR(50) NOT NULL,
    tool_nombre VARCHAR(100) NOT NULL,
    parametros  JSONB,
    status_code INT,
    error_msg   TEXT,
    latencia_ms INT,
    llamado_en  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_consumer ON audit_log(consumer_id);
CREATE INDEX idx_audit_tool     ON audit_log(tool_nombre);
CREATE INDEX idx_audit_fecha    ON audit_log(llamado_en DESC);

CREATE TABLE IF NOT EXISTS rate_limit_counter (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consumer_id    UUID        NOT NULL REFERENCES api_consumers(id),
    ventana_hora   VARCHAR(20) NOT NULL,
    total_llamadas INT         NOT NULL DEFAULT 0,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (consumer_id, ventana_hora)
);

INSERT INTO api_consumers (nombre, api_key, rol, permisos, rate_limit_hora) VALUES
(
    'María García',
    'usr-maria-garcia-a3f9k2',
    'user',
    '["cuentas:read", "gastos:read"]',
    100
),
(
    'Admin Fintech',
    'adm-fintech-x9p2m7k1',
    'admin',
    '["cuentas:read","cuentas:write","transferencias:read","transferencias:write","gastos:read","gastos:write"]',
    1000
);

-- ══════════════════════════════════════════════════════
-- NEGOCIO BANCARIO (api-fintech)
-- ══════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS clientes (
    id     VARCHAR(20)  PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS cuentas (
    id             VARCHAR(20)   PRIMARY KEY,
    cliente_id     VARCHAR(20)   NOT NULL REFERENCES clientes(id),
    tipo           VARCHAR(20)   NOT NULL CHECK (tipo IN ('ahorros', 'corriente', 'empresarial')),
    moneda         VARCHAR(5)    NOT NULL CHECK (moneda IN ('PEN', 'USD')),
    saldo          NUMERIC(15,2) NOT NULL DEFAULT 0,
    estado         VARCHAR(20)   NOT NULL DEFAULT 'activa',
    fecha_apertura DATE          NOT NULL
);

CREATE TABLE IF NOT EXISTS movimientos (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cuenta_id   VARCHAR(20)   NOT NULL REFERENCES cuentas(id),
    fecha       DATE          NOT NULL,
    descripcion VARCHAR(200)  NOT NULL,
    monto       NUMERIC(15,2) NOT NULL,
    tipo        VARCHAR(10)   NOT NULL CHECK (tipo IN ('credito', 'debito')),
    creado_en   TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_movimientos_cuenta ON movimientos(cuenta_id, fecha DESC);

CREATE TABLE IF NOT EXISTS transferencias (
    id           VARCHAR(20)   PRIMARY KEY,
    origen       VARCHAR(20)   NOT NULL REFERENCES cuentas(id),
    destino      VARCHAR(20)   NOT NULL REFERENCES cuentas(id),
    monto        NUMERIC(15,2) NOT NULL,
    moneda       VARCHAR(5)    NOT NULL,
    descripcion  VARCHAR(200)  NOT NULL DEFAULT '',
    estado       VARCHAR(20)   NOT NULL CHECK (estado IN ('COMPLETADA', 'PENDIENTE', 'FALLIDA')),
    fecha        TIMESTAMPTZ   NOT NULL,
    motivo_fallo VARCHAR(200)
);

CREATE INDEX idx_transferencias_origen  ON transferencias(origen);
CREATE INDEX idx_transferencias_destino ON transferencias(destino);

CREATE TABLE IF NOT EXISTS limites_transferencia (
    cliente_id    VARCHAR(20)   PRIMARY KEY REFERENCES clientes(id),
    limite_diario NUMERIC(15,2) NOT NULL,
    usado_hoy     NUMERIC(15,2) NOT NULL DEFAULT 0,
    moneda        VARCHAR(5)    NOT NULL
);

CREATE TABLE IF NOT EXISTS gastos_categorias (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id    VARCHAR(20)   NOT NULL REFERENCES clientes(id),
    mes           VARCHAR(7)    NOT NULL,
    categoria     VARCHAR(50)   NOT NULL,
    gastado       NUMERIC(15,2) NOT NULL DEFAULT 0,
    transacciones INT           NOT NULL DEFAULT 0,
    UNIQUE (cliente_id, mes, categoria)
);

CREATE TABLE IF NOT EXISTS presupuestos (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cliente_id VARCHAR(20)   NOT NULL REFERENCES clientes(id),
    categoria  VARCHAR(50)   NOT NULL,
    monto      NUMERIC(15,2) NOT NULL,
    UNIQUE (cliente_id, categoria)
);

-- ── Seed: clientes ────────────────────────────────────
INSERT INTO clientes (id, nombre) VALUES
('cliente-001', 'María García'),
('cliente-002', 'Carlos López'),
('cliente-003', 'Ana Torres');

-- ── Seed: cuentas ─────────────────────────────────────
INSERT INTO cuentas (id, cliente_id, tipo, moneda, saldo, estado, fecha_apertura) VALUES
('CTA-001', 'cliente-001', 'ahorros',     'PEN',  15420.50, 'activa', '2021-03-15'),
('CTA-002', 'cliente-001', 'corriente',   'USD',   3200.00, 'activa', '2022-01-10'),
('CTA-003', 'cliente-002', 'ahorros',     'PEN',   8750.00, 'activa', '2020-07-22'),
('CTA-004', 'cliente-003', 'ahorros',     'PEN',  22100.00, 'activa', '2019-11-05'),
('CTA-005', 'cliente-003', 'corriente',   'PEN',   5500.00, 'activa', '2020-02-18'),
('CTA-006', 'cliente-003', 'empresarial', 'PEN',  98000.00, 'activa', '2023-05-01');

-- ── Seed: movimientos ─────────────────────────────────
INSERT INTO movimientos (cuenta_id, fecha, descripcion, monto, tipo) VALUES
('CTA-001', '2024-11-28', 'Depósito sueldo noviembre',          4500.00, 'credito'),
('CTA-001', '2024-11-25', 'Supermercado Wong',                   -320.50, 'debito'),
('CTA-001', '2024-11-22', 'Netflix',                              -45.90, 'debito'),
('CTA-001', '2024-11-20', 'Restaurante Astrid y Gastón',         -280.00, 'debito'),
('CTA-001', '2024-11-15', 'Transferencia recibida CTA-003',       500.00, 'credito'),
('CTA-001', '2024-11-10', 'Farmacia InkaFarma',                   -89.00, 'debito'),
('CTA-001', '2024-11-05', 'Gasolina Primax',                     -150.00, 'debito'),
('CTA-002', '2024-11-20', 'Amazon.com purchase',                  -89.99, 'debito'),
('CTA-002', '2024-11-15', 'Transferencia internacional recibida',  500.00, 'credito'),
('CTA-002', '2024-11-10', 'Spotify Premium',                       -9.99, 'debito'),
('CTA-003', '2024-11-28', 'Depósito sueldo noviembre',           3200.00, 'credito'),
('CTA-003', '2024-11-25', 'Supermercado Plaza Vea',               -210.00, 'debito'),
('CTA-003', '2024-11-20', 'Transferencia enviada CTA-001',        -500.00, 'debito'),
('CTA-003', '2024-11-15', 'Recibo agua Sedapal',                   -85.00, 'debito'),
('CTA-003', '2024-11-10', 'Recibo luz Enel',                      -120.00, 'debito'),
('CTA-004', '2024-11-28', 'Depósito sueldo noviembre',           8500.00, 'credito'),
('CTA-004', '2024-11-25', 'Supermercado Vivanda',                 -450.00, 'debito'),
('CTA-004', '2024-11-22', 'Colegio mensualidad',                 -1200.00, 'debito'),
('CTA-004', '2024-11-18', 'Combustible',                          -200.00, 'debito'),
('CTA-004', '2024-11-10', 'Médico particular',                    -350.00, 'debito'),
('CTA-005', '2024-11-26', 'Pago proveedor servicios',            -2000.00, 'debito'),
('CTA-005', '2024-11-20', 'Cobro honorarios',                     3500.00, 'credito'),
('CTA-006', '2024-11-28', 'Ingreso ventas semana 4',            25000.00, 'credito'),
('CTA-006', '2024-11-21', 'Ingreso ventas semana 3',            18000.00, 'credito'),
('CTA-006', '2024-11-18', 'Pago planilla',                      -15000.00, 'debito'),
('CTA-006', '2024-11-14', 'Ingreso ventas semana 2',            22000.00, 'credito'),
('CTA-006', '2024-11-10', 'Alquiler oficina',                    -3500.00, 'debito');

-- ── Seed: transferencias ──────────────────────────────
INSERT INTO transferencias (id, origen, destino, monto, moneda, descripcion, estado, fecha) VALUES
('TRF-001', 'CTA-001', 'CTA-003',  500.00, 'PEN', 'Pago deuda',        'COMPLETADA', '2024-11-15 14:32:00'),
('TRF-002', 'CTA-004', 'CTA-001', 1000.00, 'PEN', 'Préstamo familiar', 'COMPLETADA', '2024-11-10 09:15:00'),
('TRF-003', 'CTA-006', 'CTA-005', 5000.00, 'PEN', 'Traslado operativo','PENDIENTE',  '2024-11-28 16:00:00');

INSERT INTO transferencias (id, origen, destino, monto, moneda, descripcion, estado, fecha, motivo_fallo) VALUES
('TRF-004', 'CTA-002', 'CTA-001',  200.00, 'USD', 'Conversión divisas', 'FALLIDA', '2024-11-20 11:22:00', 'Monedas incompatibles');

-- ── Seed: límites ─────────────────────────────────────
INSERT INTO limites_transferencia (cliente_id, limite_diario, usado_hoy, moneda) VALUES
('cliente-001',  5000.00,  500.00, 'PEN'),
('cliente-002',  3000.00,    0.00, 'PEN'),
('cliente-003', 50000.00, 5000.00, 'PEN');

-- ── Seed: gastos ──────────────────────────────────────
INSERT INTO gastos_categorias (cliente_id, mes, categoria, gastado, transacciones) VALUES
('cliente-001', '2024-11', 'Alimentación',     320.50, 3),
('cliente-001', '2024-11', 'Entretenimiento',  325.90, 2),
('cliente-001', '2024-11', 'Transporte',       150.00, 1),
('cliente-001', '2024-11', 'Salud',             89.00, 1),
('cliente-002', '2024-11', 'Alimentación',     210.00, 2),
('cliente-002', '2024-11', 'Servicios',        205.00, 2),
('cliente-002', '2024-11', 'Entretenimiento',    0.00, 0),
('cliente-003', '2024-11', 'Alimentación',     450.00, 1),
('cliente-003', '2024-11', 'Educación',       1200.00, 1),
('cliente-003', '2024-11', 'Transporte',       200.00, 1),
('cliente-003', '2024-11', 'Salud',            350.00, 1);

-- ── Seed: presupuestos ────────────────────────────────
INSERT INTO presupuestos (cliente_id, categoria, monto) VALUES
('cliente-001', 'Alimentación',    400.00),
('cliente-001', 'Entretenimiento', 200.00),
('cliente-001', 'Transporte',      300.00),
('cliente-002', 'Alimentación',    300.00),
('cliente-002', 'Servicios',       250.00),
('cliente-003', 'Alimentación',    500.00),
('cliente-003', 'Educación',      1000.00),
('cliente-003', 'Salud',           300.00);
