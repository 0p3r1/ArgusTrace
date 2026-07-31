function toCSV(findings) {
  const header = ['source', 'status', 'url', 'evidence']
  const escape = (value) => `"${String(value).replaceAll('"', '""')}"`
  const rows = findings.map((f) => [f.source, f.status, f.url ?? '', JSON.stringify(f.evidence ?? {})])
  return [header, ...rows].map((row) => row.map(escape).join(',')).join('\r\n')
}

export function downloadFindings(findings, filenameBase, format) {
  const content = format === 'csv' ? toCSV(findings) : JSON.stringify(findings, null, 2)
  const mime = format === 'csv' ? 'text/csv' : 'application/json'
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${filenameBase}.${format}`
  a.click()
  URL.revokeObjectURL(url)
}
