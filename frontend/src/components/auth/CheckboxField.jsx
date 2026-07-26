import './CheckboxField.css'

function CheckboxField({ checked, onChange, children, required }) {
  return (
    <label className="checkbox-field">
      <input type="checkbox" checked={checked} onChange={onChange} required={required} />
      <span className="checkbox-field__box" aria-hidden="true" />
      <span className="checkbox-field__label">{children}</span>
    </label>
  )
}

export default CheckboxField