"""Analiza danych z parsera: python -m parser.analiza --dir wyniki

Czyta produkty.json i raport.json, zapisuje do <dir>/analiza/ raport analiza.md
oraz wykresy PNG: kontrola jakości, statystyki opisowe, histogram, box-plot, korelacje.
"""
import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

NUMERIC = ("cena", "cena_pln", "ocena", "liczba_opinii", "gwarancja", "waga_g",
           "wysokosc_cm", "szerokosc_cm", "glebokosc_cm", "zuzycie_energii_w", "koszt_dostawy")
# Wartość tyle razy większa od mediany sugeruje błąd parsera, np. 129900 zamiast 1299.
PARSER_ERROR_RATIO = 50


def md_table(frame, index=True):
    frame = frame.reset_index() if index else frame
    header = "| " + " | ".join(map(str, frame.columns)) + " |"
    rule = "| " + " | ".join("---" for _ in frame.columns) + " |"
    rows = ["| " + " | ".join(format_cell(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([header, rule, *rows])


def format_cell(value):
    if isinstance(value, float):
        return f"{value:,.2f}".replace(",", " ").replace(".", ",")
    return str(value)


def quality(df, report):
    lines = ["## 1. Kontrola jakości danych", ""]
    lines += [f"- Strony listy: **{report['strony']}**, wystąpienia produktów: **{report['wystapienia']}**",
              f"- Duplikaty przed odrzuceniem: **{report['duplikaty_usuniete']}**, "
              f"po odrzuceniu: **{int(df['id'].duplicated().sum())}**",
              f"- Rekordy: **{len(df)}**, atrybuty danych: **{report['atrybuty']}**, "
              f"błędy pobierania: **{report['bledy']}**, czas: **{report['czas_s']} s**", ""]

    gaps = pd.DataFrame({
        "braki": df.isna().sum(),
        "braki_%": (df.isna().mean() * 100).round(1),
        "odrzucone_przez_walidacje": pd.Series(report["odrzucone"]),
        "typ": df.dtypes.astype(str),
    })
    gaps["odrzucone_przez_walidacje"] = gaps["odrzucone_przez_walidacje"].fillna(0).astype(int)
    lines += ["### Braki i typy kolumn", "", md_table(gaps.rename_axis("kolumna")), ""]

    wrong_types = [c for c in NUMERIC if c in df and not pd.api.types.is_numeric_dtype(df[c])]
    lines += ["Kolumny liczbowe faktycznie liczbowe: " +
              ("**tak**" if not wrong_types else f"**nie**: {', '.join(wrong_types)}"), ""]

    lines += ["### Wartości odstające (reguła 1,5·IQR)", ""]
    rows = []
    for column in NUMERIC:
        values = df[column].dropna()
        q1, q3 = values.quantile([.25, .75])
        low, high = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
        median = values.median()
        for idx, value in values[(values < low) | (values > high)].items():
            suspicious = median and value / median > PARSER_ERROR_RATIO
            rows.append({"kolumna": column, "id": df.at[idx, "id"], "kategoria": df.at[idx, "kategoria"],
                         "wartosc": value,
                         "mediana": median, "interpretacja": "podejrzenie błędu parsera"
                         if suspicious else "prawdziwa wartość z ogona rozkładu"})
    lines += [md_table(pd.DataFrame(rows), index=False) if rows else "Brak wartości odstających.", ""]
    return lines, rows


def descriptive(df):
    stats = pd.DataFrame({
        "średnia": df[list(NUMERIC)].mean(),
        "mediana": df[list(NUMERIC)].median(),
        "moda": df[list(NUMERIC)].mode().iloc[0],
        "Q1": df[list(NUMERIC)].quantile(.25),
        "Q3": df[list(NUMERIC)].quantile(.75),
        "min": df[list(NUMERIC)].min(),
        "max": df[list(NUMERIC)].max(),
    })
    return ["## 2. Statystyki opisowe", "",
            "Kolumna `cena` miesza waluty (PLN i EUR), do porównań służy `cena_pln`.", "",
            md_table(stats.rename_axis("cecha")), ""]


def plots(df, out):
    paths = []

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(df["cena_pln"].dropna(), bins=20, color="#2f6b4f", edgecolor="white")
    ax.set(title="Histogram cen (PLN)", xlabel="cena [PLN]", ylabel="liczba produktów")
    paths.append(save(fig, out / "histogram_cena_pln.png"))

    order = df.groupby("kategoria")["cena_pln"].median().sort_values().index
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.boxplot([df.loc[df["kategoria"] == k, "cena_pln"].dropna() for k in order], tick_labels=order)
    ax.set(title="Cena wg kategorii (PLN)", ylabel="cena [PLN]")
    ax.tick_params(axis="x", rotation=30)
    paths.append(save(fig, out / "boxplot_cena_kategoria.png"))

    numeric = df[[c for c in NUMERIC if c != "cena"]]
    corr = numeric.corr()
    fig, ax = plt.subplots(figsize=(8, 7))
    image = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr)), corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr)), corr.columns)
    for i in range(len(corr)):
        for j in range(len(corr)):
            value = corr.iat[i, j]
            ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=7,
                    color="white" if abs(value) > .6 else "black")
    fig.colorbar(image, ax=ax)
    ax.set_title("Macierz korelacji Pearsona")
    paths.append(save(fig, out / "korelacja.png"))

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, (x, y) in zip(axes, (("waga_g", "cena_pln"), ("liczba_opinii", "ocena"))):
        ax.scatter(df[x], df[y], s=12, color="#2f6b4f", alpha=.7)
        ax.set(xlabel=x, ylabel=y, title=f"{y} vs {x} (r = {df[x].corr(df[y]):.2f})")
    paths.append(save(fig, out / "rozrzut.png"))
    return corr, paths


def save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def correlation_lines(corr):
    pairs = corr.where(~pd.DataFrame(
        [[i >= j for j in range(len(corr))] for i in range(len(corr))], index=corr.index, columns=corr.columns))
    pairs = pairs.stack().rename("r").to_frame()
    pairs["|r|"] = pairs["r"].abs()
    top = pairs.sort_values("|r|", ascending=False).head(8).drop(columns="|r|")
    top.index = [f"{a} – {b}" for a, b in top.index]
    return ["## 4. Korelacje", "", "Najsilniejsze pary cech (Pearson):", "",
            md_table(top.rename_axis("para")), ""]


def main(argv=None):
    args = argparse.ArgumentParser(description="Analiza danych z parsera katalogu Północ.")
    args.add_argument("--dir", default="wyniki", help="katalog z produkty.json i raport.json")
    options = args.parse_args(argv)

    source = Path(options.dir)
    df = pd.DataFrame(json.loads((source / "produkty.json").read_text(encoding="utf-8")))
    report = json.loads((source / "raport.json").read_text(encoding="utf-8"))
    out = source / "analiza"
    out.mkdir(parents=True, exist_ok=True)

    lines = ["# Analiza danych — katalog Północ", ""]
    quality_lines, outliers = quality(df, report)
    lines += quality_lines + descriptive(df)
    corr, paths = plots(df, out)
    lines += ["## 3. Wykresy", ""] + [f"![{p.stem}]({p.name})" for p in paths] + [""]
    lines += correlation_lines(corr)
    (out / "analiza.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"Rekordy: {len(df)}, wartości odstające: {len(outliers)}, wyniki: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
