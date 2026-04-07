# Appliance Training Session Guide

`Appliance Training Session` is the training page of the `NILM` app.

It prepares appliance training data from Home Assistant history and sends the job to the configured training server.

## What This Page Is For

Use this page when you want to create a new appliance model from historical data.

The page currently supports:

- choosing the training server
- choosing an appliance name
- selecting a supervision mode
- selecting a history range
- preparing a training payload
- sending the job to the training server
- tracking training progress

## Training Stepper

The page includes a stepper to guide the workflow.

The current stages are:

- `Server`
- `Appliance`
- `Labels`
- `Prepare`
- `Train`

This helps you see what is already complete before sending a training job.

## Help Modal

The `?` button near the page title opens a help modal explaining how the training session works.

This is intended as quick guidance inside the UI. The current document goes into more detail.

## Training Server Connection

The `Training Server Connection` card is the first thing to check.

What to do:

1. confirm the training server is detected or available
2. select the desired training server
3. click `Save`
4. confirm the card shows the server as ready

If the internal training app is installed, it is shown as an internal option in the selector.

Important:

- detection alone does not activate the server
- the user must still select the server and save the choice

## Mains Power Signal

The training page includes a mains chart for the selected training interval.

This chart is used to:

- inspect the aggregate signal
- mark intervals manually in interval supervision mode
- compare the mains signal with a ground-truth appliance sensor in sensor supervision mode

## Supervision Modes

The page supports two different supervision modes.

### 1. Interval Supervision

In interval supervision, you manually indicate the periods where the target appliance is ON.

Use this mode when:

- you do not have a dedicated appliance sensor
- you want full manual control of the labels
- the appliance pattern is easy to identify visually in mains

Typical flow:

1. choose the target appliance name
2. choose the history range
3. inspect the mains signal
4. create ON intervals manually
5. prepare the training job
6. send it to the training server

### 2. Ground-Truth Appliance Sensor

In sensor supervision mode, you choose a Home Assistant appliance sensor that represents the target appliance directly.

Use this mode when:

- you already have a dedicated appliance sensor
- you want to derive labels from a real appliance signal
- you want faster and more reproducible labeling than manual interval creation

In this mode, the training chart can display the ON intervals derived from the sensor.

These intervals now use the exact backend Python logic used during training preparation, which makes them suitable for debugging.

## Sensor-Derived ON Intervals

When a ground-truth appliance sensor is used, the ON intervals shown in the chart come from the same backend labeling logic used for the training payload.

That logic:

- aligns the sensor to the training grid
- builds the sensor-derived ON mask
- bridges short OFF gaps
- then removes short ON runs

This order is important because it helps bursty appliances remain labeled as ON when they have repeated short activations separated by short OFF gaps.

## Preparing The Training Job

Once the appliance, supervision mode, and history range are ready, use the prepare action to build the training payload.

The preparation step:

- fetches the mains history
- aligns the data to the model sampling grid
- creates the input windows
- filters invalid windows
- builds the embeddings needed for training
- creates the target labels

After preparation, the UI shows whether the job is ready to send.

## Sending The Training Job

When you send the job:

1. the NILM app stores the prepared job locally
2. it uploads the job to the `NILM Training Server`
3. the training server runs the training job in the background
4. the NILM app polls the job until it finishes
5. the trained appliance model is saved inside `NILM`

When the job succeeds, the new model appears in `Energy Dashboard`.

## What Happens After Training

After training completes:

- the new appliance model is stored in the NILM app
- the app computes deployment metrics for the model
- the deployed on/off threshold is derived from the edge runtime replay
- the model becomes available in `Energy Dashboard`

This is important because the deployed threshold is based on the runtime actually used by NILM, not only on the trainer-side result.

## Model Quality

The dashboard shows `Training Quality` for each appliance model.

This is intended as a useful indicator, not as the only truth about the model.

A good workflow is:

1. train the appliance
2. open `Energy Dashboard`
3. preview the same interval with `Disaggregate`
4. compare the predicted behavior with the expected appliance activity

## Good Training Practices

### Use Meaningful Appliance Names

Use names that clearly identify the appliance, for example:

- `fridge`
- `electric_oven`
- `dishwasher`

The name is reused in:

- the dashboard model card
- the stored model file
- the live Home Assistant entities

### Start With A Focused Range

For a first model, choose a range that clearly contains representative appliance activity.

Shorter and cleaner ranges are usually easier to debug than long noisy ones.

### Prefer Sensor Supervision When Available

If you have a good ground-truth appliance sensor, it is usually the easiest and most reproducible way to train.

### Use Interval Supervision For Hard Cases

Manual intervals are useful when:

- no appliance sensor exists
- the appliance signature is easy to identify visually
- you want precise manual control over the label intervals

## Debugging Training With The Chart

The training chart is useful for:

- confirming that the selected mains range contains the appliance activity
- comparing the appliance sensor against mains
- checking whether the sensor-derived ON intervals make sense
- verifying that the intervals used for training are not obviously wrong

If the displayed intervals look wrong in sensor supervision mode, the issue is usually related to:

- the quality of the ground-truth appliance sensor
- the chosen time range
- the appliance behavior itself

## Training Server Notes

The training server is separate from the NILM app on purpose.

This keeps the main NILM app more stable for:

- live inference
- dashboard usage
- Home Assistant operation

Training is heavier and can use significantly more memory and CPU than normal inference.

