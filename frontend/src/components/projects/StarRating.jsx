import './StarRating.css'

function StarRating({ rating = 0, size = 13 }) {
  const stars = [1, 2, 3, 4, 5]
  return (
    <span className="star-rating" style={{ fontSize: size }}>
      {stars.map((n) => (
        <span
          key={n}
          className={`star-rating__star ${n <= Math.round(rating) ? 'star-rating__star--filled' : ''}`}
        >
          ★
        </span>
      ))}
    </span>
  )
}

export default StarRating