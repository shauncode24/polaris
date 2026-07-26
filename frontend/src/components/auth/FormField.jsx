import './FormField.css'

function FormField({ label, type = 'text', value, onChange, placeholder, required, autoComplete, error }) {
  return (
    <label className={`form-field ${error ? 'form-field--error' : ''}`}>
      {label && <span className="form-field__label">{label}</span>}
      <input
        className="form-field__input"
        type={type}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        required={required}
        autoComplete={autoComplete}
      />
      {error && <span className="form-field__error">{error}</span>}
    </label>
  )
}

export default FormField