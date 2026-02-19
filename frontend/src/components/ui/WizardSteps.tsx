interface WizardStepsProps {
  steps: { label: string }[]
  current: number
  skippedSteps?: number[]
}

export function WizardSteps({ steps, current, skippedSteps = [] }: WizardStepsProps) {
  return (
    <div className="flex items-start">
      {steps.map((step, i) => {
        const isDone = i < current
        const isActive = i === current
        const isSkipped = skippedSteps.includes(i)
        const isLast = i === steps.length - 1

        return (
          <div key={i} className="flex items-start flex-1 min-w-0">
            {/* Step circle + label */}
            <div className="flex flex-col items-center">
              <div
                className={`
                  w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium flex-shrink-0
                  ${isSkipped
                    ? 'border border-border text-text-dim'
                    : isDone
                      ? 'bg-accent-cyan text-bg'
                      : isActive
                        ? 'border-2 border-accent-cyan text-accent-cyan'
                        : 'border border-border text-text-dim'
                  }
                `}
              >
                {isSkipped ? '\u2013' : i + 1}
              </div>
              <span
                className={`
                  mt-2 text-xs text-center break-words max-w-[5rem]
                  ${isActive ? 'text-text font-semibold' : 'text-text-muted'}
                `}
              >
                {step.label}
              </span>
            </div>

            {/* Connecting line */}
            {!isLast && (
              <div className="flex-1 flex items-center pt-4 px-2">
                <div
                  className={`h-0.5 w-full rounded-full ${isDone ? 'bg-accent-cyan' : 'bg-border'}`}
                />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
