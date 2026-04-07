# Energy Dashboard Guide

`Energy Dashboard` is the main operational page of the `NILM` app.

It is used to:

- choose the mains sensor
- inspect recent mains history
- review trained appliance models
- preview appliance disaggregation on historical ranges
- compare the contribution of multiple appliance predictions
- enable or disable live publishing per model

## Main Areas Of The Page

The page is organized around three main tasks.

### 1. Mains Signal Selection And Visualization

At the top of the page you can:

- choose the mains sensor
- select the history range
- inspect the mains chart

The chart is interactive and supports:

- zoom
- pan
- touch interaction on mobile

This chart is the base view for previewing disaggregation results.

### 2. Appliance Models

The `Appliance Models` section lists the trained appliance models currently stored in the app.

For each model, the card shows information such as:

- appliance name
- training quality
- live publishing state

Each card includes a `Disaggregate` button to preview that appliance on the selected mains interval.

The section also includes:

- a `Models` summary
- a `Disaggregate All` button

`Disaggregate All` runs the available models over the selected interval and plots them together.

## Mains Chart Behavior

When the page first loads:

- the chart shows the mains signal over the selected range
- the chart fits to the first and last real data points

When a prediction is added:

- the predicted appliance line is drawn on top of the mains chart
- the prediction uses the same chart, not a separate modal
- the chart keeps its interactive zoom and pan behavior

Multiple appliance predictions can be shown at the same time.

## Prediction Chips

Below the chart, each active appliance prediction appears as a removable chip.

These chips are useful because they:

- show which appliance predictions are currently plotted
- make it easy to remove one prediction without clearing the others
- serve as the visual key for the appliance colors used in the chart

The mains series stays in the chart by default.

## Tooltip Information

When you hover a predicted appliance line in the chart, the tooltip shows:

- predicted appliance power
- predicted on/off state
- on/off probability `p`
- deployed on/off threshold `thr`

This is useful for debugging and understanding why a predicted power value is kept or clamped to zero.

## Live Publishing

Each appliance model can be configured to publish live Home Assistant entities.

When live publishing is enabled for a model:

- NILM creates a power sensor for the appliance
- NILM creates a binary on/off sensor for the appliance

The live binary state uses the saved optimal on/off threshold from the model metadata, not a fixed threshold.

## Disaggregate One Appliance

To preview one appliance:

1. load the desired mains range
2. find the appliance model card
3. click `Disaggregate`
4. wait for the prediction progress to complete
5. inspect the appliance line on the chart

Use this mode when you want:

- the most detailed inspection
- a clear view of one appliance versus mains
- debugging of on/off probability and threshold behavior

## Disaggregate All Models

`Disaggregate All` runs all available appliance models on the selected range.

This is useful when you want to:

- get a broad overview of the whole set of models
- compare several appliances at once
- update the appliance share diagram quickly

This mode is heavier than a single-appliance preview because it creates and transfers multiple prediction series at once.

For large ranges or many trained models, it uses more CPU, time, and memory.

## Appliance Share Diagram

When predictions are available, the dashboard shows a pastel share diagram representing the mains composition.

It includes:

- each added appliance prediction
- `Base Load`
- `Other`

### Base Load

`Base Load` is the part of the mains that behaves like always-on consumption, such as standby devices or appliances that continuously draw power.

### Other

`Other` is the remaining mains energy not explained by the currently plotted appliance predictions and base load.

The share diagram updates dynamically when:

- a prediction is added
- a prediction is removed
- multiple appliances are disaggregated

## Mobile Usage

The dashboard is designed to remain usable on phones.

Current mobile behavior includes:

- two-column stats cards
- automatic scrolling back to the chart after starting a prediction
- touch interaction on the chart
- full-width model summary layout

## Practical Advice

- Start by disaggregating one appliance before using `Disaggregate All`.
- Use shorter history ranges when debugging a model.
- Use the chart tooltip when checking threshold behavior.
- Use `Disaggregate All` mainly for overview, not for the most precise inspection.

