function pdfString(line) {
  return String(line).normalize("NFD").replace(/\p{Mark}/gu, "")
    .replace(/[^\x20-\x7E]/g, "-").replace(/[()\\]/g, "\\$&");
}

export function downloadDemoPdf({filename, lines}) {
  const text = [...lines, "", "Donnees fictives - document sans valeur officielle"]
    .map((line, index) => `${index ? "T* " : ""}(${pdfString(line)}) Tj`).join("\n");
  const stream = "BT /F1 14 Tf 20 TL 50 780 Td\n" + text + "\nET\n";
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    `<< /Length ${stream.length} >>\nstream\n${stream}endstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let pdf = "%PDF-1.4\n";
  const offsets = objects.map((object, index) => {
    const offset = pdf.length;
    pdf += `${index + 1} 0 obj\n${object}\nendobj\n`;
    return String(offset).padStart(10, "0") + " 00000 n \n";
  });
  const xref = pdf.length;
  pdf += `xref\n0 6\n0000000000 65535 f \n${offsets.join("")}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;

  const BlobURL = URL;
  const url = BlobURL.createObjectURL(new Blob([pdf], {type:"application/pdf"}));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => BlobURL.revokeObjectURL(url), 1000);
}
