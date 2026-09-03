"""Explicit adapter registry with deterministic, confidence-based detection."""
_adapters={}


def register(adapter):
    if adapter.adapter_id in _adapters:raise RuntimeError(f'Adaptador duplicado: {adapter.adapter_id}')
    _adapters[adapter.adapter_id]=adapter
    return adapter


def available():return tuple(_adapters.values())

def get(adapter_id):
    try:return _adapters[adapter_id]
    except KeyError:raise ValueError('Adaptador desconhecido') from None


def detect(filename,body):
    matches=sorted(((adapter.detect(filename,body),adapter.adapter_id,adapter)
                    for adapter in _adapters.values()),reverse=True)
    matches=[match for match in matches if match[0]>0]
    if not matches:raise ValueError('Nenhum adaptador reconheceu este arquivo')
    if len(matches)>1 and matches[0][0]==matches[1][0]:
        raise ValueError('Formato ambíguo; mais de um adaptador reconheceu o arquivo')
    return matches[0][2],matches[0][0]
