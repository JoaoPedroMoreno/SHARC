import pathlib

import pdfplumber


FILES = [
    r"C:\Users\joaop\OneDrive\Documentos\PIBIC 2025\Contribuitions\DC-MSS downlink and FS in the frequency band 1 .pdf",
    r"C:\Users\joaop\OneDrive\Documentos\PIBIC 2025\Contribuitions\DCMSS-EESS - Sys 1 a 3.pdf",
    r"C:\Users\joaop\OneDrive\Documentos\PIBIC 2025\Contribuitions\DC-MSS-IMT_vs_IMT-terrestrial_2110-2170MHz_Sharing_WP4C_draft_nm_v4.pdf",
]


def main() -> None:
    out_dir = pathlib.Path("tmp/pdfs/dcmss_refs")
    out_dir.mkdir(parents=True, exist_ok=True)
    for file_name in FILES:
        path = pathlib.Path(file_name)
        chunks = []
        with pdfplumber.open(path) as pdf:
            for page_number, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                chunks.append(f"\n\n===== PAGE {page_number} =====\n{text}")
        output_path = out_dir / f"{path.stem}.txt"
        output_path.write_text("".join(chunks), encoding="utf-8")
        print(f"{path.name}: {len(chunks)} pages -> {output_path}")


if __name__ == "__main__":
    main()
