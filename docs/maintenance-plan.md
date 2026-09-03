# Manutenção: proposta para aprovação

Estado observado em 03/09/2026: volume de 7,8 GB com 3,6 GB livres,
1,1 GB em backups, 454 MB em releases e 278 MB na restauração de teste.

## Retenção local proposta

- Manter os 7 backups diários mais recentes.
- Manter os 3 backups anteriores a atualizações mais recentes.
- Manter as 3 releases mais recentes e sempre a release ativa.
- Preservar diretórios desconhecidos, links e backups incompletos para inspeção.
- Não excluir automaticamente a instalação inicial nem a restauração de teste.

`scripts/retention_plan.py` produz somente uma prévia JSON e não remove arquivos.
Recebe `--backups`, `--releases` e `--active`, todos caminhos explícitos.
A contagem não é uma garantia de espaço livre: medir o crescimento e emitir alerta
antes de falta de espaço. Backups pré-atualização podem depender de código mais
antigo; manter esse código no repositório Git e não executar garbage collection
que elimine commits de recuperação.

Antes de habilitar exclusões: aprovar a política, verificar integridade dos
backups retidos e comprovar recuperação de uma cópia externa. A futura execução
deve usar o mesmo lock de backup/implantação e verificar novamente a release ativa.

## Cópia externa e HTTPS

Destino aprovado: `//rpi5.lan/mergerfs/Backup/Fin2`, equivalente no servidor a
`/mnt/MERGERFS/Backup/Fin2`. A transferência utiliza SSH, sem gravar senha SMB.
Endereço externo: `https://django.lmnet.qzz.io/fin2/`. A consulta anônima retornou
redirecionamento para Cloudflare Access; o acesso autenticado e o encaminhamento
ao container ainda precisam ser verificados. Não remover essa proteção.
Não reutilizar o próprio container como cópia externa. A chave de recuperação
deve ficar fora dele. O backup exportado precisa abranger banco, documentos,
imagens e configuração, com teste de restauração e descriptografia.

Ao configurar TLS, preservar a restrição de LAN/VPN e ativar cookies seguros,
origens CSRF e cabeçalhos do proxy apropriados. Não expor o dashboard sem login
à Internet apenas porque passou a utilizar HTTPS.

O exemplo de ambiente foi atualizado apenas em desenvolvimento. Antes de ativar,
identificar o proxy de origem e confiar em X-Forwarded-Proto somente vindo dele;
o Nginx atual sobrescreve esse cabeçalho com o esquema HTTP local. Cookies seguros
também exigirão HTTPS para os formulários; não ativar isoladamente enquanto o uso
local HTTP continuar necessário.

Envio pontual de backup autorizado pelo usuário. A cópia é cifrada com GPG/AES256,
com senha aleatória guardada em `~/Fin2-private/recovery/backup-passphrase.txt`
no computador de desenvolvimento, nunca no destino compartilhado. Guardar outra
cópia dessa senha em um cofre seguro: sem ela o backup não pode ser recuperado.
Para recuperar: `gpg --output fin2.tar.gz --decrypt ARQUIVO.tar.gz.gpg`, informar
a senha no prompt, extrair em diretório isolado e verificar o manifesto com
`scripts/fin2_backup.py verify DIRETORIO_DO_SNAPSHOT`.

Automação da cópia externa e ativação das mudanças de HTTPS permanecem pendentes.
Não houve exclusões, commit ou push.

## Preparação da automação

`deploy/export-backup.sh` verifica o snapshot, cifra com uma chave pública GPG,
transfere para um nome temporário via SSH e verifica SHA-256 antes de publicar
o arquivo definitivo. Não sobrescreve arquivos existentes. O recibo local só é
gravado após confirmação remota. Erros propagam falha ao serviço de backup.
O Fin2 é reiniciado antes da etapa externa; a cópia não prolonga sua parada.

Para ativar após aprovação:

1. Gerar um par de chaves de criptografia em ambiente seguro; manter a chave
   privada e sua senha em um cofre fora da produção e do NAS. A primeira cópia
   manual continua usando a senha simétrica já entregue; não a descartar.
2. Importar apenas a chave pública em `/etc/fin2/gnupg` e informar o fingerprint
   completo em `/etc/fin2/backup.env`, usando o exemplo versionado.
3. Criar chave SSH dedicada em `/etc/fin2/backup_ed25519`, configurar acesso ao
   destino e registrar a chave de host verificada em `/etc/fin2/backup_known_hosts`.
   Restringir a credencial à transferência de backups sempre que possível.
4. Instalar os scripts e a unidade revisada, testar com snapshot sintético,
   verificar descriptografia fora do container e só então habilitar a rotina.

Não copiar a chave privada GPG para produção. O exportador exige chave pública
justamente para manter a capacidade de recuperação separada da aplicação.
Validação atual: sintaxe Bash e quatro testes de backup/retenção aprovados;
o envio automático com chave pública ainda não foi executado.

## Encaminhamento HTTPS identificado

Cloudflared ativo no rpi3 encaminha `*.lmnet.qzz.io` para 127.0.0.1:80.
A porta 80 pertence ao container nginx-ui. Não foi encontrada regra Django nos
sites ativos desse container. Preparadas propostas específicas para rpi3 e
t1django; nenhum proxy foi alterado. O t1django só aceita o cabeçalho HTTPS
encaminhado pelo IP 10.0.0.3, evitando confiar nesse cabeçalho vindo de qualquer
cliente da LAN.

Antes de ativar, validar a política Cloudflare Access, o bloqueio de acesso
direto externo ao proxy e o fluxo autenticado no navegador, incluindo POST/CSRF.
Cookies seguros exigem usar HTTPS nos formulários de produção; o desenvolvimento
local permanece HTTP e não receberá essa configuração.
