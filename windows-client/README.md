# Elysius Shield Client - Windows

Aplicativo para gerenciar seu acesso ao servidor Elysius RP automaticamente.

## Funcionalidades

- **Processo Completo**: Gera código, aguarda validação no Discord, e salva sessão automaticamente
- **System Tray**: Fica minimizado na barra de tarefas do Windows
- **Renovação Automática**: Renova seu IP automaticamente a cada 60 segundos
- **Troca de IP**: Detecta quando seu IP muda e atualiza automaticamente
- **Notificações**: Mostra status de conexão, códigos e erros

## Como Usar

### Primeira Vez

1. **Execute o programa** - aparece um ícone na system tray (área de notificação)
2. **Clique com botão direito** no ícone
3. **Clique em "Obter Novo Código"**
4. Uma notificação aparece com um código de 4 letras (ex: `AB12`)
5. **Vá ao Discord** e digite esse código no canal de shield
6. O programa detecta automaticamente quando validado
7. **Pronto!** A sessão é salva e renovada automaticamente

### Após a Primeira Vez

- O programa lembra sua sessão (válida por 15 dias)
- Basta executar e ele renova automaticamente
- Se o IP mudar, atualiza sozinho
- Se a sessão expirar, clique em "Obter Novo Código"

## Cores do Ícone

| Cor | Significado |
|-----|-------------|
| 🟢 Verde | Conectado e funcionando |
| 🔵 Azul | Aguardando código no Discord |
| 🟡 Amarelo | Renovando sessão |
| 🔴 Vermelho | Erro ou sessão expirada |
| ⚪ Cinza | Desconectado |

## Menu (Clique Direito)

- **Obter Novo Código**: Solicita um código para validar no Discord
- **Renovar Agora**: Força renovação imediata
- **Verificar Status**: Mostra informações da sessão
- **Abrir Portal**: Abre o portal no navegador
- **Abrir Configuração**: Abre a pasta de config
- **Ver Log**: Abre o arquivo de log
- **Limpar Sessão**: Remove a sessão salva
- **Sair**: Encerra o programa

## Instalação

### Opção 1: Executável Pronto
1. Baixe o `ElysiusShield.exe`
2. Execute (não precisa instalar)

### Opção 2: Compilar do Código
1. Instale Python 3.10+
2. Na pasta `windows-client`, execute `build.bat`
3. O executável estará em `dist\ElysiusShield.exe`

## Iniciar com o Windows

1. Pressione `Win + R`
2. Digite `shell:startup` e pressione Enter
3. Copie o `ElysiusShield.exe` (ou crie um atalho) para essa pasta

## Configuração Avançada

O arquivo de configuração fica em:
```
%APPDATA%\ElysiusShield\config.json
```

```json
{
  "portal_url": "https://shield.elysiusrp.com.br",
  "refresh_interval": 60,
  "session_token": "...",
  "discord_name": "Usuario#1234",
  "last_ip": "123.456.789.0"
}
```

| Campo | Descrição | Padrão |
|-------|-----------|--------|
| `portal_url` | URL do portal | `https://shield.elysiusrp.com.br` |
| `refresh_interval` | Segundos entre renovações | `60` |
| `session_token` | Token (gerenciado automaticamente) | - |
| `discord_name` | Nome do Discord (salvo automaticamente) | - |
| `last_ip` | Último IP usado | - |

## Resolução de Problemas

### "Muitas tentativas"
- Você tentou gerar muitos códigos
- Aguarde 5 minutos e tente novamente

### "Sessão expirada"
- Sua sessão de 15 dias expirou
- Clique em "Obter Novo Código"

### Código não é validado
- Verifique se digitou o código correto no Discord
- O código expira em 5 minutos
- Use letras MAIÚSCULAS no Discord

### "Erro de conexão"
- Verifique sua internet
- Verifique se o portal está online

### Arquivo de Log

Problemas? Verifique o log em:
```
%APPDATA%\ElysiusShield\client.log
```

## Requisitos

- Windows 10/11
- Conexão com internet
- Conta no Discord do Elysius RP

## Suporte

- Discord: discord.gg/elysiusrp
- Abra um ticket no Discord para problemas técnicos
