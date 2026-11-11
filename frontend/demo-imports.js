const columns = [
  ["last_name", "Nom", ["nom", "last name"]],
  ["first_name", "Prénoms", ["prenom", "prenoms", "first name"]],
  ["date_of_birth", "Date de naissance", ["date de naissance", "ddn"]],
  ["classroom", "Classe", ["classe", "classroom"]],
  ["guardian_name", "Nom du responsable", ["nom parent", "nom du responsable", "responsable"]],
  ["guardian_phone", "Téléphone du responsable", ["telephone parent", "telephone du responsable"]],
  ["guardian_email", "Courriel du responsable", ["email parent", "courriel du responsable"]],
];
const choices = columns.map(([value, label]) => ({value, label}));
const normalize = value => String(value).trim().normalize("NFD").replace(/\p{Mark}/gu, "").toLowerCase();
const cellText = value => value instanceof Date ? value.toISOString().slice(0, 10) : String(value ?? "").trim();

async function readUpload(file, sheet, headerRow) {
  if (!file?.name || !file.size || file.size > 3 * 1024 * 1024) throw Error("Choisissez un fichier fictif de 3 Mio maximum.");
  const isExcel = /\.xlsx$/i.test(file.name);
  if (!isExcel && !/\.csv$/i.test(file.name)) throw Error("Format fictif attendu : CSV ou XLSX.");
  let sheets = [];
  let data;
  if (isExcel) {
    const {default: readExcel} = await import("read-excel-file/universal");
    const workbook = await readExcel(file);
    sheets = workbook.map(item => item.sheet);
    data = (workbook.find(item => item.sheet === sheet) || workbook[0])?.data;
  } else {
    const {default: csv} = await import("papaparse");
    const parsed = csv.parse(await file.text(), {delimitersToGuess: [",", ";", "\t"]});
    if (parsed.errors.some(error => error.code !== "UndetectableDelimiter")) throw Error("CSV fictif mal formé.");
    data = parsed.data;
  }
  if (!Number.isInteger(headerRow) || headerRow < 1 || headerRow > 10 || !data?.[headerRow - 1])
    throw Error("La ligne d’en-tête est introuvable.");
  const headers = data[headerRow - 1].map(cellText);
  const rows = data.slice(headerRow).map((row, index) => ({
    line: headerRow + index + 1, cells: row.map(cellText)
  })).filter(row => row.cells.some(Boolean));
  if (!rows.length || rows.length > 500) throw Error("Le fichier fictif doit contenir de 1 à 500 élèves.");
  return {headers, rows, sheets, sheet: sheets.includes(sheet) ? sheet : sheets[0] || ""};
}

export function createDemoImports() {
  const profiles = [];
  const previews = new Map();
  const completed = new Set();
  let sequence = 0;

  return async function handle(action, school, form, context) {
    const {classrooms, years, defaultYear, register} = context;
    if (action === "profiles") return {profiles:profiles.filter(row => row.school === school)};
    if (action === "export") {
      const {default: csv} = await import("papaparse");
      const year = form.year;
      const rows = context.students.filter(row => !year || row.year === year && row.level).map(row => {
        const split = row.name.indexOf(" ");
        return [row.name.slice(0, split), row.name.slice(split + 1), row.date_of_birth || "",
          row.level, row.guardian, row.phone];
      });
      const output = csv.unparse([["Nom", "Prénoms", "DDN", "Classe", "Nom parent", "Téléphone parent"], ...rows],
        {delimiter:";", escapeFormulae:true});
      return new Response("\uFEFF" + output, {headers:{"content-type":"text/csv; charset=utf-8"}});
    }
    const headerRow = Number(form.get("header_row"));
    const input = await readUpload(form.get("file"), form.get("sheet"), headerRow);
    if (action === "inspect") {
      const suggested_mapping = Object.fromEntries(input.headers.flatMap((header, index) => {
        const match = columns.find(([, , aliases]) => aliases.includes(normalize(header)));
        return match ? [[index, match[0]]] : [];
      }));
      return {headers:input.headers, header_row:headerRow, sheet:input.sheet, sheets:input.sheets,
        row_count:input.rows.length, samples:input.rows.slice(0, 3).map(row => row.cells),
        years:years.filter(year => year.active), choices, suggested_mapping};
    }
    const mapping = JSON.parse(form.get("mapping") || "{}");
    const year = form.get("year");
    const selected = Object.values(mapping);
    if (!selected.includes("first_name") || !selected.includes("last_name") ||
      new Set(selected).size !== selected.length || selected.some(key => !choices.some(choice => choice.value === key)))
      throw Error("Associez une seule colonne à chaque champ, dont le nom et les prénoms.");
    if (year && !years.some(row => row.id === year && row.active)) throw Error("Année fictive indisponible.");
    const fingerprint = JSON.stringify([school, year, input.headers, input.rows, mapping]);
    const token = form.get("token");
    if (action === "commit" && previews.get(token) !== fingerprint) throw Error("Recalculez l’aperçu de ce fichier.");
    if (action === "commit" && completed.has(fingerprint)) return {already_imported:true, imported:0};
    const identities = new Set(context.students.map(row => normalize(row.name)));
    const candidates = [];
    const rows = input.rows.map(({line, cells}) => {
      const row = Object.fromEntries(Object.entries(mapping).map(([index, field]) => [field, cells[index] || ""]));
      const name = [row.last_name, row.first_name].filter(Boolean).join(" ");
      const room = row.classroom && year ? classrooms.find(item => item.year === year &&
        normalize(item.name) === normalize(row.classroom)) : null;
      const key = normalize(name);
      let error = "";
      if (!row.first_name || !row.last_name) error = "Nom et prénoms obligatoires.";
      else if (identities.has(key)) error = "Un dossier porte déjà ce nom.";
      else if (row.classroom && year && !room) error = "Classe introuvable pour cette année.";
      identities.add(key);
      if (!error) candidates.push({row, room});
      return {line, name, valid:!error, error, class:room?.name || "",
        warning:!error && !row.guardian_name ? "Responsable à renseigner." : ""};
    });
    const errors = rows.filter(row => !row.valid).length;
    if (action === "preview") {
      const token = "import-demo-" + (++sequence);
      previews.set(token, fingerprint);
      return {rows, token, valid:candidates.length, errors, warnings:rows.filter(row => row.warning).length};
    }
    if (errors) return {error:"Corrigez les lignes invalides avant de confirmer.", rows};
    for (const {row, room} of candidates) register({
      student:{first_name:row.first_name, last_name:row.last_name, date_of_birth:row.date_of_birth || null},
      guardians:row.guardian_name ? [{full_name:row.guardian_name, phone:row.guardian_phone || "",
        email:row.guardian_email || ""}] : [],
      enrollment:room ? {classroom:room.id} : null,
    }, year || defaultYear);
    const templateName = form.get("template_name")?.trim();
    if (templateName) profiles.push({id:token, school, name:templateName, headers:input.headers, mapping});
    completed.add(fingerprint);
    return {imported:candidates.length, notice:"Les dossiers fictifs sont disponibles pour cette visite."};
  };
}
