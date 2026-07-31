function OptionInput({ option, value, onChange }) {
  const current = value !== undefined ? value : option.default

  switch (option.type) {
    case 'int':
      return (
        <input
          type="number"
          min={option.min}
          max={option.max}
          value={value ?? ''}
          placeholder={option.default !== null && option.default !== undefined ? String(option.default) : ''}
          onChange={(e) => onChange(e.target.value === '' ? undefined : Number(e.target.value))}
        />
      )
    case 'bool':
      return (
        <input
          type="checkbox"
          checked={Boolean(current)}
          onChange={(e) => onChange(e.target.checked)}
        />
      )
    case 'enum':
      return (
        <select value={value ?? ''} onChange={(e) => onChange(e.target.value || undefined)}>
          <option value="">(default{option.default ? `: ${option.default}` : ''})</option>
          {option.choices.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      )
    case 'enum_multi': {
      const selected = value ?? option.default ?? []
      return (
        <div className="option-multi-group">
          {option.choices.map((c) => (
            <label key={c} className="option-multi-item">
              <input
                type="checkbox"
                checked={selected.includes(c)}
                onChange={(e) => {
                  const next = e.target.checked ? [...selected, c] : selected.filter((x) => x !== c)
                  onChange(next)
                }}
              />
              {c}
            </label>
          ))}
        </div>
      )
    }
    case 'str':
    default:
      return (
        <input
          type="text"
          value={value ?? ''}
          placeholder={option.default ? String(option.default) : ''}
          onChange={(e) => onChange(e.target.value === '' ? undefined : e.target.value)}
        />
      )
  }
}

function OptionField({ option, value, onChange }) {
  return (
    <div className="option-field">
      <label className="option-label">
        <span className="option-flag">{option.flag}</span>
        <span className={`option-tag ${option.required ? 'required' : 'optional'}`}>
          {option.required ? 'required' : 'optional'}
        </span>
      </label>
      <p className="option-description">{option.description}</p>
      <OptionInput option={option} value={value} onChange={onChange} />
    </div>
  )
}

export default function AdvancedOptionsPanel({ family, values, onChange, defaultOpen = false }) {
  if (!family || !family.options || family.options.length === 0) return null

  return (
    <details className="advanced-options" open={defaultOpen || undefined}>
      <summary>Options ({family.options.length})</summary>
      <div className="advanced-options-body">
        {family.options.map((opt) => (
          <OptionField
            key={opt.name}
            option={opt}
            value={values[opt.name]}
            onChange={(v) => onChange(opt.name, v)}
          />
        ))}
      </div>
    </details>
  )
}
