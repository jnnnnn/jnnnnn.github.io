# Retirement Calculator Specification

A financial calculator inspired by Mike Bostock's [NYT Buy vs Rent Calculator](https://www.nytimes.com/interactive/2014/upshot/buy-rent-calculator.html), featuring live-updating sliders where each parameter shows its effect on retirement outcomes. All values expressed in **today's dollars** (inflation-adjusted).

## Core Design Principles

1. **Transparency**: The calculation logic is visible and editable as JavaScript in a text box on the page
2. **Immediate feedback**: Every slider change instantly updates all outputs
3. **Contextual indicators**: Each slider shows a mini-visualization of how that parameter affects the final result
4. **Smooth UI**: 60fps animations, no jank, visually polished

---

## Input Parameters

### The Basics

| Parameter | Default | Range | Units |
|-----------|---------|-------|-------|
| Current age | 30 | 18–80 | years |
| Retirement age | 65 | 40–80 | years |
| Life expectancy | 90 | 70–110 | years |
| Current savings | $50,000 | $0–$5M | dollars |
| Annual salary | $80,000 | $0–$500k | dollars |
| **Desired monthly retirement income** | $5,000 | $1k–$20k | dollars/month |

### Contributions

| Parameter | Default | Range | Units |
|-----------|---------|-------|-------|
| Contribution rate | 10% | 0–50% | % of salary |
| Employer match | 50% | 0–100% | % of contribution |
| Match cap | 6% | 0–10% | % of salary |

### Market Assumptions

| Parameter | Default | Range | Units |
|-----------|---------|-------|-------|
| Nominal investment return | 7% | 0–15% | % per year |
| Inflation rate | 3% | 0–10% | % per year |
| Salary growth (real) | 1% | 0–5% | % per year above inflation |

### Taxes

| Parameter | Default | Range | Units |
|-----------|---------|-------|-------|
| Income tax rate | 20% | 0–50% | effective rate on withdrawals |

---

## The Calculation Function

The calculation is defined as an **editable JavaScript function** displayed in a `<textarea>` on the page. Users can modify it to add complexity (taxes, Roth conversions, etc.).

### Default Function

```javascript
function calculate(inputs) {
  const {
    currentAge, retirementAge, lifeExpectancy,
    currentSavings, annualSalary,
    contributionRate, employerMatchRate, matchCap,
    nominalReturn, inflationRate, realSalaryGrowth,
    incomeTaxRate,
    desiredMonthlyIncome  // THE KEY INPUT (after-tax spending)
  } = inputs;

  // Real (inflation-adjusted) return
  const realReturn = (1 + nominalReturn) / (1 + inflationRate) - 1;

  // Build year-by-year projection
  // Continue past life expectancy to find when money actually runs out
  const maxAge = 120;
  const years = [];
  let portfolio = currentSavings;
  let salary = annualSalary;
  let moneyRunsOutAge = null;

  for (let age = currentAge; age <= maxAge; age++) {
    const year = { age, portfolioStart: portfolio, salary };

    if (age < retirementAge) {
      // Accumulation phase: contribute to portfolio
      const employeeContrib = salary * contributionRate;
      const employerContrib = salary * Math.min(contributionRate, matchCap) * employerMatchRate;
      const totalContrib = employeeContrib + employerContrib;

      portfolio = portfolio * (1 + realReturn) + totalContrib;
      salary = salary * (1 + realSalaryGrowth); // Already real terms
      year.contribution = totalContrib;
    } else {
      // Withdrawal phase: withdraw fixed amount to meet desired after-tax income
      // Gross withdrawal = after-tax income / (1 - tax rate)
      const desiredAfterTax = desiredMonthlyIncome * 12;
      const grossWithdrawal = desiredAfterTax / (1 - incomeTaxRate);
      
      // Can only withdraw what's available
      const actualWithdrawal = Math.min(grossWithdrawal, portfolio);
      const afterTaxIncome = actualWithdrawal * (1 - incomeTaxRate);
      
      portfolio = (portfolio - actualWithdrawal) * (1 + realReturn);
      year.grossWithdrawal = actualWithdrawal;
      year.afterTaxIncome = afterTaxIncome;
      year.monthlyIncome = afterTaxIncome / 12;
      year.incomeShortfall = desiredAfterTax - afterTaxIncome;
    }

    year.portfolioEnd = Math.max(0, portfolio);
    years.push(year);

    // Track when money runs out
    if (portfolio <= 0 && moneyRunsOutAge === null) {
      moneyRunsOutAge = age;
    }
    
    // Stop if we're past life expectancy AND money has run out
    if (age > lifeExpectancy && portfolio <= 0) {
      break;
    }
  }

  // Key outputs
  const atRetirement = years.find(y => y.age === retirementAge);
  
  // THE PRIMARY OUTPUT: Years of buffer (or shortfall)
  // Positive = money lasts X years beyond life expectancy
  // Negative = money runs out X years before life expectancy
  // null = money never runs out (within simulation)
  let yearsOfBuffer;
  if (moneyRunsOutAge === null) {
    yearsOfBuffer = Infinity; // Money never runs out
  } else {
    yearsOfBuffer = moneyRunsOutAge - lifeExpectancy;
  }

  return {
    years,
    
    // PRIMARY OUTPUT: How many years of buffer (or shortfall) you have
    yearsOfBuffer,              // +5 = "money lasts 5 years past life expectancy"
                                 // -10 = "money runs out 10 years before life expectancy"
                                 // Infinity = "money never runs out"
    
    // Supporting details
    portfolioAtRetirement: atRetirement?.portfolioEnd ?? 0,
    moneyRunsOutAge,            // null if money never runs out
    desiredMonthlyIncome,
    lifeExpectancy,
  };
}
```

### How it's displayed

```
┌─────────────────────────────────────────────────────────────────┐
│ Calculation Function                                    [Reset] │
├─────────────────────────────────────────────────────────────────┤
│ function calculate(inputs) {                                    │
│   const { currentAge, retirementAge, ... } = inputs;            │
│   ...                                                           │
│ }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

- Syntax-highlighted with a simple theme (or use CodeMirror/Monaco for richer editing)
- **[Reset]** button restores the default function
- Parse errors shown inline with red highlighting
- Function is re-evaluated on every keystroke (debounced 300ms)

---

## Mini-Indicator Design (The Key Innovation)

Each slider has a **sensitivity indicator** showing how much the final result changes when you adjust that parameter. This answers: *"How much does this slider matter?"*

### Visual Design

The indicator shows the **years of buffer** across the slider's range:

```
Annual Salary                                               $80,000
├──────────────────────────●───────────────────────────────────────┤
$0                                                            $500k

              ╭───────────────────────────────────╮
              │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░│
              ╰───────────────────────────────────╯
            -15 yrs                           +20 yrs
                          ▲
                     Current: +5 yrs
```

- **Red zone** (left): Settings where money runs out before life expectancy
- **Green zone** (right): Settings where money lasts past life expectancy
- **Zero crossing**: Where you exactly meet life expectancy
- **Current marker**: Shows where your current setting lands

### Indicator Specifications

1. **Horizontal bar** beneath each slider, showing the range of `yearsOfBuffer` outcomes
2. **Left edge**: years of buffer if slider is at minimum value
3. **Right edge**: years of buffer if slider is at maximum value  
4. **Zero line**: A vertical line where buffer = 0 (money lasts exactly to life expectancy)
5. **Current position marker**: A bright vertical line showing where current settings land
6. **Color coding**: 
   - **Red** for shortfall (negative buffer = runs out before life expectancy)
   - **Green** for buffer (positive = lasts past life expectancy)
   - The bar is split at the zero line, not at current position
7. **Labels**: Show the min/max buffer values at edges (`-15 yrs → +20 yrs`)
8. **Current value callout**: Text showing current buffer (e.g., `+5 yrs`)
9. **Infinity handling**: If money never runs out, show `∞` or cap display at `+30 yrs`

### Implementation Details

```javascript
function calculateSensitivity(paramName, currentValue, minValue, maxValue) {
  const steps = 20; // Sample 20 points across the range
  const results = [];
  
  for (let i = 0; i <= steps; i++) {
    const testValue = minValue + (maxValue - minValue) * (i / steps);
    const testInputs = { ...currentInputs, [paramName]: testValue };
    const result = calculate(testInputs);
    results.push({
      inputValue: testValue,
      // Cap infinity at a reasonable display value
      buffer: Math.min(result.yearsOfBuffer, 30),
    });
  }
  
  // Find where buffer crosses zero (money lasts exactly to life expectancy)
  const zeroIndex = results.findIndex((r, i) => 
    i > 0 && results[i-1].buffer < 0 && r.buffer >= 0
  );
  
  return { results, zeroIndex };
}
```

### Visual Rendering (SVG)

```html
<svg class="sensitivity-indicator" width="300" height="24">
  <!-- Background track -->
  <rect x="0" y="8" width="300" height="8" fill="#e0e0e0" rx="4"/>
  
  <!-- Gradient fill showing outcome range -->
  <defs>
    <linearGradient id="sensitivity-grad-salary">
      <stop offset="0%" stop-color="#ef4444"/>   <!-- Red: worse -->
      <stop offset="48%" stop-color="#fbbf24"/>  <!-- Yellow: neutral -->
      <stop offset="52%" stop-color="#fbbf24"/>
      <stop offset="100%" stop-color="#22c55e"/> <!-- Green: better -->
    </linearGradient>
  </defs>
  <rect x="0" y="8" width="300" height="8" fill="url(#sensitivity-grad-salary)" rx="4"/>
  
  <!-- Current position marker -->
  <line x1="150" y1="4" x2="150" y2="20" stroke="#1e40af" stroke-width="3"/>
  
  <!-- Min/max labels -->
  <text x="0" y="22" font-size="10" fill="#666">$1.2M</text>
  <text x="300" y="22" font-size="10" fill="#666" text-anchor="end">$2.8M</text>
</svg>
```

### Alternative: Sparkline Chart

For parameters with non-linear effects, show a tiny **sparkline** instead of a gradient bar:

```
Nominal Return                                                   7%
├──────────────────────────●──────────────────────────────────────┤
0%                                                              15%

         ╭──╮
        ╱    ╲
       ╱      ──────   ← Portfolio at 65 across return values
──────╱
$0.5M              $4M
```

This reveals:
- **Exponential relationships** (compound growth)
- **Inflection points** (e.g., where portfolio runs out)
- **Diminishing returns** (e.g., salary above a certain level doesn't help if match is capped)

### The Single Output Metric

All indicators show the same thing: **Years of Buffer**

This is how long your money lasts compared to your life expectancy:

```
Years of Buffer = Age When Money Runs Out − Life Expectancy
```

- **+5 years** = Money lasts until age 95 (5 years past life expectancy of 90)
- **-10 years** = Money runs out at age 80 (10 years before life expectancy of 90)
- **∞** = Money never runs out (portfolio grows faster than withdrawals)

This metric is intuitive: positive is good, negative is bad, zero means you're exactly on track.

---

## Primary Visualization: Timeline Chart

A D3.js area chart showing **portfolio value** over time:

```
Portfolio Value (Today's Dollars)
│
$2M ┤                    ╭───────╮
    │                   ╱        ╲
$1.5M┤                 ╱          ╲
    │                ╱            ╲
$1M ┤         ╭─────╯              ╲
    │        ╱                      ╲
$500k┤      ╱                        ╲
    │     ╱                          ╲
$0  ┼────╯────────────────────────────╲─────────────
    30      40      50      60      70│     80      90      100  Age
                            │         │              │
                        Retirement  Money         Life
                                   runs out    expectancy
```

### Features

- **Shaded area** under the portfolio curve
- **Color transition**: Green while money lasts, fades to red as it depletes
- **Vertical dashed lines** at key ages:
  - Current age ("Today")
  - Retirement age
  - Life expectancy
  - Age when money runs out (if applicable)
- **Hover tooltip** showing portfolio value, monthly income, and buffer at any age
- **Smooth transitions** when inputs change (D3 transition, 300ms ease-out)

---

## The Big Number: Primary Result Display

At the top of the page, prominently display the key result:

```
┌────────────────────────────────────────────────────────────┐
│                                                            │
│                      +8 years buffer                       │
│                                                            │
│      Your money lasts 8 years past life expectancy         │
│                                                            │
│    Money lasts to: 98    Life expectancy: 90               │
│    Portfolio at 65: $1,860,000                             │
│    Monthly income: $5,000 (after 20% tax)                  │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

Or if there's a shortfall:

```
┌────────────────────────────────────────────────────────────┐
│                                                            │
│                     -12 years short                        │
│                                                            │
│      Your money runs out 12 years before life expectancy   │
│                                                            │
│    Money runs out at: 78    Life expectancy: 90            │
│    Portfolio at 65: $820,000                               │
│    Monthly income: $5,000 (after 20% tax)                  │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

Or if money never runs out:

```
┌────────────────────────────────────────────────────────────┐
│                                                            │
│                       ∞ Forever                            │
│                                                            │
│      Your portfolio grows faster than your spending        │
│                                                            │
│    Portfolio at 65: $3,200,000                             │
│    Monthly income: $5,000 (after 20% tax)                  │
│    Portfolio at 90: $4,100,000 (still growing!)            │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### Styling

- **Large font** for the years number (48px+)
- **Green background** when positive, **red background** when negative, **gold** for infinity
- **Animates smoothly** when value changes
- Updates in real-time as sliders move

---

## Technical Implementation

### Stack

- **HTML/CSS/JS** (no build step, single file or minimal files)
- **D3.js v7** for the timeline chart and transitions
- **CSS custom properties** for theming
- **localStorage** to persist user's inputs and custom function

### File Structure

```
retirement/
├── index.html      # Main page
├── spec.md         # This specification
└── README.md       # Usage instructions
```

### Performance

- **Main calculation**: Runs synchronously (~60 iterations, <1ms)
- **Sensitivity indicators**: 20 samples × 11 parameters = 220 calculations per update
  - Total: ~13,200 loop iterations per slider move
  - Still fast enough (<50ms) for smooth interaction
- **Optimization strategies**:
  - Cache sensitivity results; only recalculate for the slider being dragged
  - Debounce sensitivity recalculation to every 100ms during drag
  - Use `requestAnimationFrame` for chart updates
  - Consider Web Workers if targeting slower devices
