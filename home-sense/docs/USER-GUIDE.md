# Haven: setup and demonstration guide

Haven presents radar reflections in a home layout, opens a room in 3D and logs motion review events. The saved ESP capture is real; replay does not establish live sensing today. People counts, recognized activities, falls and vital signs remain unavailable.

## 1. Open your workspace

Double-click `Start Haven.command` in the home-sense folder, then open http://127.0.0.1:8768 on this computer. Enter your profile and home name. In Setup, use **Create workspace password** if you want sign-in protection. Choose your own password; there is no preset account.

The example room layout is editable and is not a scan of your house. Start in **Replay** to demonstrate the saved 6 October ESP data without changing hardware.

## 2. Add your scanned space

In **Setup**, choose **Import Polycam export**. Prefer a self-contained GLB; a GLTF requires its companion geometry and image files. OBJ geometry is also supported. Select all necessary files together. The combined limit is 150 MB.

Choose the active scan and set **Metres per model unit**. Set **Scan vertical axis** to the export’s Y-up or Z-up convention, and use **Scan floor rotation** to align it with the plan. These controls transform the displayed scan without changing the source file. Align the room rectangles with your scan and name each room. Room boundaries are manual: the app does not automatically identify walls or rooms. Room-specific model binding supports separately scanned rooms.

**Your home at a glance** now automatically fits the active scan's measured geometry, rather than the example room layout. Its size updates when you import/select another scan or change units, vertical axis or floor rotation. Sensor coordinates use the same projection. Room labels appear only when associated with this scan and contained within its footprint; otherwise the dashboard opens the whole **Scanned space** in 3D. Editing a room in Setup associates its plan boundary with the active scan. The file does not provide automatic room names.

Scan files are saved in the workspace service. Authenticated devices can retrieve them from that service once secure device access is configured. This computer's localhost address cannot be opened directly from a phone. Actual phone deployment and scan rendering still require verification.

## 3. Place a radar module

Add a module in Setup, enter its mounting height and orientation, then select it in the placement control and tap the scan at its actual installed position. The map supplies its coordinates and assigns the containing room. If no rooms have been defined, Haven saves a neutral **Scanned space** extent measured from the GLB; it does not invent room names. Name or divide that space in Room boundaries. Named room regions replace the whole-scan boundary on the map. Overlapping regions or unmarked gaps need correction before assignment.

Sensor positions are tied to their scan and saved alignment. Selecting another scan or changing units, vertical axis or floor rotation requires placing sensors again; readings from an unrelated scan are excluded from this plan. Existing default-alignment positions remain visible only for their associated scan. New modules start unassigned until placed on the GLB. The first room form can use the measured scan extent without requesting manual dimensions. Zero degrees points down the plan; 90 degrees points right. Check the physical axes before treating the display as measured location. Actual tapping/rendering remains unverified.

Hover over a room for its details, or hold it for about half a second on a touch screen. Releasing a hold keeps the details visible. A quick tap or click opens its 3D view. Scrolling cancels the hold. Keyboard focus reveals details; Enter or Space opens the room. Dots represent candidate reflection groups, not confirmed people. Trails show observed association between reports, not a person's identity. Phone touch and rendered 3D behavior have not yet been verified.

The room view keeps a shared home scan in its original home coordinates. A separately imported room scan is anchored at that room's plan origin. Its sensor markers use saved mounting height, and only sensors and current reflection groups inside the selected room appear. Trail runs stop at excursions outside that room; the display does not join disconnected runs into a shortcut. If an assigned room file is unavailable, Haven identifies the fallback to the home scan or schematic geometry. These coordinate rules have geometry checks; actual rendering and physical alignment remain unverified.

## 4. Present the recorded demo

1. Select **Replay** and play the recorded capture.
2. Show changing reflection groups and room details, then open the 3D room.
3. Explain that reports may contain more reflections than the console's visible coordinates. Incomplete previews remain labelled.
4. Enable **Away mode** and inspect source-labelled motion review events in **Activity log**.
5. Return to **At home** after the demonstration.

A useful presentation statement is: “This prototype demonstrates radar acquisition, spatial visualization and a motion review rule. Human recognition and care measurements require further acquisition and validation.”

## 5. Try fresh ESP input

Keep the previously verified wiring and firmware. Close other serial monitors before connecting through **Sensors**. Select the intended module and its ESP serial port, then connect. The service must verify the firmware and a real radar reply before scanning.

Choose a finite scan for a bench demonstration. **Start persistent monitoring** repeats finite scans with setup gaps; **Stop** disables future cycles. Faults disable repetition. It is not uninterrupted home coverage. Do not interpret stale, disconnected or zero-point reports as proof that a room is empty.

If the port is busy, release it in the application that currently owns it. USB enumeration alone does not prove radar communication. A new live capture must be verified before presenting it as live.

For a controlled activity experiment, finish the finite scan and stop monitoring, then use **Prepare an activity session** in Sensors. Enter a session identifier, participant pseudonym and observed activity, then choose **Save to Haven**. Open it in **Saved activity recordings**, inspect its quality, write observation notes and mark it reviewed only when you observed that activity throughout. Exclude interrupted or mixed trials. **Export reviewed dataset** retains the original readings and review history for offline training. Labels are your notes, not detections. See [DATA-COLLECTION.md](DATA-COLLECTION.md) for collection and [TRAINING-COMPATIBILITY.md](TRAINING-COMPATIBILITY.md) for the experiment workflow.

For wireless sensor delivery, **Connect over home Wi-Fi** provides pairing controls for the selected module. A key alone does not connect the board: its Wi-Fi firmware needs your home network settings and Haven's reachable HTTPS address. Follow [ESP-WIFI.md](ESP-WIFI.md). The firmware is prepared but has not been uploaded or verified over real Wi-Fi.

## 6. Manage a trial

In **Trial safeguards**, select **Add trial** and enter the service name, actual start date, duration, renewal fee and reminder interval from your receipt. The app calculates expiry and reminders three, two and one day before it. Check the displayed renewal date against the provider's account; date-only reminders do not establish the provider's billing time.

**Export calendar reminders** downloads three reminder events for import into your calendar. Google Calendar/Tasks account integration is outside the current scope at your request. Imported reminders follow your calendar's notification settings; priority does not guarantee delivery.

High-priority desktop reminders repeat while Haven is open and cancellation is unverified. Closing the app stops this desktop loop. Phone-alert setup is deferred at your request; no phone delivery is configured or verified. **Cancellation pending** keeps reminders active. Cancel through the provider, save the confirmation, enter its reference and select **Mark cancelled & verified**. Haven records your verification; it does not cancel the subscription or independently check the provider.

## When something is unavailable

- A missing scan file or companion resource produces an error and a labelled schematic fallback. Reimport the original export when files are missing.
- Care measurements stay unavailable until supported and validated; switching on a care setting does not enable fall or vital-sign measurement.
- Away events ask for review of moving reflections. They do not confirm a person or an intrusion.
- Authentication, TLS deployment and integration configuration are covered in SECURE-DEPLOYMENT.md and INTEGRATIONS.md. No real remote notification service is connected by default.

### Recording coverage before training

Sensors → Saved activity recordings now counts reviewed recordings, participants, activities and radar modules. The per-participant/module list exposes missing activities across recorded pairs. Keep a consistent participant ID for each person. The offline training workflow needs at least three distinct participants for separate training, validation and test groups, and at least two activity classes in training. Collection counts alone do not prove usable windows or accuracy: final timing checks and held-out evaluation still run offline. No live recognition is enabled by saving/reviewing data.
