import { motion } from 'framer-motion'

/** Glass button whose highlight follows the pointer and which squashes like liquid when pressed. */
export default function Liquid({ as = 'a', primary = false, children, ...props }) {
  const Tag = motion[as]
  const track = e => {
    const r = e.currentTarget.getBoundingClientRect()
    e.currentTarget.style.setProperty('--x', `${e.clientX - r.left}px`)
    e.currentTarget.style.setProperty('--y', `${e.clientY - r.top}px`)
  }
  return (
    <Tag
      className={`liquid${primary ? ' primary' : ''}`}
      onPointerMove={track}
      whileHover={{ scale: 1.035 }}
      whileTap={{ scaleX: 1.06, scaleY: 0.92 }}
      transition={{ type: 'spring', stiffness: 420, damping: 18, mass: 0.6 }}
      {...props}
    >
      {children}
    </Tag>
  )
}
