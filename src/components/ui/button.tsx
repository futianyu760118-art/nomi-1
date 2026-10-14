import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '../../lib/utils'

const buttonVariants = cva(
  'btn inline-flex items-center justify-center gap-2 disabled:pointer-events-none',
  {
    variants: { variant: { default: 'primary', secondary: 'secondary', ghost: 'ghost' } },
    defaultVariants: { variant: 'default' },
  },
)

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, asChild = false, ...props }, ref) => {
    const Component = asChild ? Slot : 'button'
    return <Component className={cn(buttonVariants({ variant, className }))} ref={ref} {...props} />
  },
)
Button.displayName = 'Button'
