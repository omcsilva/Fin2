# Ciclo produtivo e recuperação

Este procedimento cobre preparação, implantação, validação, retorno à versão
anterior e restauração de dados. Execute comandos de produção em `t1django.lan`.

## Preparar e implantar

No desenvolvimento, confirme que somente os arquivos pretendidos estão no diff,
execute as verificações e publique um commit identificável:

~~~bash
git status --short
git diff --check
.venv/bin/python manage.py check
.venv/bin/python -m unittest discover -s tests -q
git push origin main
git rev-parse HEAD
~~~

Ative exatamente o hash retornado:

~~~bash
ssh mcsil@t1django.lan "sudo /usr/local/sbin/update-fin2 HASH_COMPLETO"
~~~

A rotina prepara uma release isolada, cria e verifica um snapshot pré-atualização,
para o serviço, aplica migrações, troca a release, testa o HTTP local e exporta o
snapshot cifrado. Uma falha depois da parada deixa o serviço parado para impedir
que código e esquema incompatíveis sejam usados juntos.

## Validar

~~~bash
sudo systemctl is-active fin2
sudo cat /var/lib/fin2/deployed-revision
curl --fail http://127.0.0.1:8020/fin2/ -o /dev/null
sudo systemctl status fin2-backup.timer fin2-retention.timer fin2-health.timer
sudo /usr/local/sbin/check-fin2-health
~~~

Confirme também o HTTPS em `https://django.lmnet.dpdns.org/fin2/`. Consulte os
logs sem imprimir dados financeiros:

~~~bash
sudo journalctl -u fin2 -n 50 --no-pager
sudo journalctl -u fin2-health.service -n 20 --no-pager
~~~

## Testar uma restauração isolada

Escolha um snapshot íntegro, nunca o diretório de dados ativo. O destino deve não
existir:

~~~bash
snapshot=/var/backups/fin2/AAAAmmddTHHMMSSZ
restore=/var/lib/fin2-restore-test-AAAAmmdd
sudo /opt/fin2/.venv/bin/python /opt/fin2/scripts/fin2_backup.py verify "$snapshot"
sudo /opt/fin2/.venv/bin/python /opt/fin2/scripts/fin2_backup.py restore "$snapshot" "$restore"
sudo -u fin2 /opt/fin2/.venv/bin/python -c "import duckdb; c=duckdb.connect('$restore/fin2.duckdb',read_only=True); print(c.execute('select count(*) from schema_migration').fetchone()[0]); c.close()"
sudo diff -r "$snapshot/data/documents" "$restore/documents"
sudo diff -r "$snapshot/data/catalog-images" "$restore/catalog-images"
~~~

Quando banco, documentos e imagens conferirem, registre a validação no snapshot
e remova apenas o diretório isolado. O marcador faz essa cópia participar da
retenção como referência restaurável:

~~~bash
sudo touch "$snapshot/restore-validated"
sudo rm -rf --one-file-system "$restore"
~~~

A cópia cifrada externa deve ser baixada e decifrada em uma máquina de recuperação
que possua a chave privada. Depois de extrair o arquivo, execute a mesma verificação
e restauração isolada. A chave privada não deve ser copiada para `t1django` ou rpi5.

## Recuperar produção

Se apenas o código falhou e não houve migração, reimplante um commit compatível.
Se o esquema ou os dados mudaram, use o snapshot pré-atualização correspondente:

~~~bash
sudo systemctl stop fin2
sudo mv /var/lib/fin2 /var/lib/fin2-failed-AAAAmmddTHHMMSSZ
sudo /opt/fin2/.venv/bin/python /opt/fin2/scripts/fin2_backup.py restore "$snapshot" /var/lib/fin2
sudo chown -R fin2:fin2 /var/lib/fin2
sudo systemctl start fin2
sudo /usr/local/sbin/check-fin2-health
~~~

Preserve o diretório com falha até concluir a reconciliação. Reimplante a release
compatível com o snapshot e confirme a revisão ativa, o HTTP local e o HTTPS.

## Estado observado em 07/09/2026

O serviço usava cerca de 124 MB de RSS entre mestre e worker, em um container de
2 GB com 1,7 GB disponíveis. O disco estava em 57%, com 8,1 GB livres. A base e
arquivos ativos ocupavam 287 MB; backups, 6,7 GB; releases, 457 MB.

Os backups diários recentes duraram entre 46 e 67 segundos de relógio e consumiram
entre 28 e 32 segundos de CPU após habilitar a exportação. A implantação de
`f2ba0eb1f79cf76abd935e18e256140f27e177ff` deixou o HTTP indisponível por cerca
de sete segundos. O serviço voltou com HTTP 200 e a cópia cifrada foi confirmada.

Treze snapshots pré-atualização antigos não possuem comprovante externo e são
preservados pela retenção para inspeção. Eles ocupam aproximadamente 3,6 GB. Os
novos snapshots possuem recibo externo e seguem a janela automática configurada.

Uma atualização manual completa de preços em 07/09/2026 processou 66 ativos e
ignorou 90 conforme as regras de elegibilidade. Todos os 66 foram aceitos, sem
rejeição ou falha, em 7 minutos e 10 segundos. Durante a amostragem, mestre e
worker do Gunicorn atingiram aproximadamente 166 MB de RSS e 12,4% de CPU
agregado. A espera de cinco segundos entre chamadas domina a duração do trabalho.
