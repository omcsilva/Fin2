# Ferramentas de migração

## Cópia de trabalho do Fin1

`backup_fin1.py` executa `fin1_snapshot_remote.py` por SSH e recebe uma cópia em uma pasta nova, obrigatoriamente fora deste repositório. Requer Python 3.12+ local, Python 3.11+ remoto e autenticação SSH previamente configurada. Não instala dependências.

Exemplo no PowerShell, a partir da raiz do Fin2:

```powershell
python scripts/backup_fin1.py --host mcsil@rpi5.lan --source /home/mcsil/Fin1 --destination C:\Users\mcsil\Fin2-private\snapshots\NOVO-NOME
```

A pasta de destino não pode existir. Não reutilize o exemplo literalmente sem escolher um nome novo. A ferramenta não remove nem sobrescreve backups anteriores.

### Procedimento

1. Calcula hashes e metadados dos três SQLite, seus sidecars presentes e arquivos de `ANEXOS`.
2. Usa a API SQLite de backup com conexões de origem somente leitura.
3. Copia anexos para uma pasta temporária privada no servidor e verifica seus hashes.
4. Compara novamente o inventário de origem; interrompe sem entregar o arquivo se detectar alterações.
5. Verifica integridade, chaves estrangeiras e contagens dos bancos copiados.
6. Transmite um TAR por SSH e remove a pasta temporária remota ao sair normalmente.
7. Extrai em `restored/`, confere todos os hashes e repete as verificações SQLite localmente.
8. Grava `verification.json` somente após concluir as verificações.

O arquivo `snapshot.tar` é a cópia preservada; use outra cópia dos bancos restaurados para trabalhos que precisem escrever. `restored/manifest.json` contém nomes privados de arquivos, hashes e contagens. Não adicione esses arquivos ao Git.

### Limites e falhas

Não há parada de serviço nem bloqueio coordenado da aplicação. Igualdade de hashes e metadados antes/depois detecta alterações observáveis, mas não constitui uma transação atômica entre bancos e filesystem. Este procedimento atende à preparação de uma base de desenvolvimento; a captura final para cutover deve ocorrer em janela coordenada, impedindo novas gravações.

Se o processo falhar, a pasta local pode conter um TAR parcial ou extração incompleta. Não use uma cópia sem `verification.json` com `verified: true`. Preserve os arquivos para diagnóstico e escolha outro destino ao tentar novamente. A limpeza local é deliberadamente manual; a ferramenta nunca apaga backups.

Esta cópia inclui os bancos completos, inclusive tabelas legadas de autenticação. Proteja o diretório com as permissões do sistema e criptografia de disco. Não contém o código-fonte, `.env` ou configuração completa de implantação, portanto não substitui um plano de recuperação integral do Fin1.
