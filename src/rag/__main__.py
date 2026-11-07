"""
Punto de entrada de `python -m rag`. Prepara el corpus sin calcular embeddings.

Funciones:
- main(): Ejecuta la preparación y resume páginas y fragmentos.
"""

from .preparar import preparar_corpus


def main() -> None:
    res = preparar_corpus(reescribir=True)
    print("UTC", res["generado_utc"])
    print("originales", res["originales"])
    print("salidas", res["salidas"])
    print("paginas", res["n_paginas"], "fragmentos", res["n_fragmentos"])
    for d in res["documentos"]:
        print(
            d["doc_id"],
            "paginas", d.get("n_paginas"),
            "ok", d.get("n_paginas_ok"),
            "vacias", d.get("n_paginas_vacias"),
            "cortas", d.get("n_paginas_cortas"),
            "sospechosas", d.get("n_paginas_sospechosas"),
            "fragmentos", d.get("n_fragmentos"),
            "error", d.get("error"),
        )
    for e in res["excluidos"]:
        print("excluido", e["archivo"], "conservado", e["conservado"])
    frag = res["fragmentos"]
    print("fragment_id unicos", frag["fragment_id"].nunique())
    print("calidad fragmentos")
    print(frag["calidad"].value_counts().to_string())
    print("calidad paginas")
    print(res["paginas"]["calidad"].value_counts().to_string())


if __name__ == "__main__":
    main()
