export function findingsToCSV(findings) {
  const header = ['source', 'status', 'url', 'evidence']
  const escape = (value) => `"${String(value).replaceAll('"', '""')}"`
  const rows = findings.map((f) => [f.source, f.status, f.url ?? '', JSON.stringify(f.evidence ?? {})])
  return [header, ...rows].map((row) => row.map(escape).join(',')).join('\r\n')
}

export function findingsToJSON(findings) {
  return JSON.stringify(findings, null, 2)
}

export function findingsContent(findings, format) {
  return format === 'csv' ? findingsToCSV(findings) : findingsToJSON(findings)
}

export function downloadFindings(findings, filenameBase, format) {
  const content = findingsContent(findings, format)
  const mime = format === 'csv' ? 'text/csv' : 'application/json'
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${filenameBase}.${format}`
  a.click()
  URL.revokeObjectURL(url)
}
