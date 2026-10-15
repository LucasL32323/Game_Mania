DROP DATABASE IF EXISTS game_mania;
CREATE DATABASE game_mania;
USE game_mania;

CREATE TABLE usuarios (
id INT AUTO_INCREMENT PRIMARY KEY,
nome VARCHAR(100) NOT NULL,
email VARCHAR(100) NOT NULL UNIQUE,
senha_hash VARCHAR(255) NOT NULL,
is_admin BOOLEAN DEFAULT FALSE,
data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE produtos (
id INT AUTO_INCREMENT PRIMARY KEY, 
nome VARCHAR(150) NOT NULL,
preco DECIMAL(10,2) NOT NULL,
imagem_url varchar(255),
estoque INT DEFAULT 0
);

CREATE TABLE pedidos (
id INT AUTO_INCREMENT PRIMARY KEY,
usuario_id INT NOT NULL,
valor_total DECIMAL(10,2) NOT NULL,
status ENUM('pendente','pago','enviado','cancelado') DEFAULT 'pendente',
data_pedido DATETIME DEFAULT CURRENT_TIMESTAMP,
FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
);

CREATE TABLE itens_pedido(
id INT AUTO_INCREMENT PRIMARY KEY,
pedido_id INT NOT NULL,
produto_nome VARCHAR(150) NOT NULL,
preco_unitario DECIMAL(10,2) NOT NULL,
quantidade INT NOT NULL,
FOREIGN KEY (pedido_id) REFERENCES pedidos(id)
);