-- =============================================
-- ADICIONAR USUÁRIO ADMINISTRADOR
-- Email: admin@loja.com
-- Senha: 123456
-- =============================================

-- Hash da senha "123456" usando bcrypt
-- Gerado com: python3 -c "import bcrypt; password = '123456'; hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()); print(hashed.decode('utf-8'))"
INSERT INTO usuarios (nome, email, senha_hash, role, ativo) 
VALUES (
    'Administrador',
    'admin@loja.com', 
    '$2b$12$UbW5ozueXcOl5VEcGhNOv.5VVyUrdBsFqEYqVe.kdrQIrqOec00Xi', -- senha: 123456
    'ADMIN',
    TRUE
)
ON CONFLICT (email) DO UPDATE SET
    senha_hash = '$2b$12$UbW5ozueXcOl5VEcGhNOv.5VVyUrdBsFqEYqVe.kdrQIrqOec00Xi',
    role = 'ADMIN',
    ativo = TRUE,
    updated_at = CURRENT_TIMESTAMP;