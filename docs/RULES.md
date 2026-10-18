# Sabis ("Service"): rulebook (living document)

Sabis is a street game from Kano, northern Nigeria. This rulebook records the rules **as they are
implemented in the engine**. It is a working draft: rules are added or changed as we watch the game
being played, and every change should be noted in the CHANGELOG. Where a rule here came from the
engine's authors rather than from players, it is marked **(draft)** and should be checked against
how the game is really played in Kano.

## 1. The ball

A disc cut from a slipper, with its edge beveled at an angle using the sharp lid of a Peak Milk
can. The bevel makes it curve as it rolls. Equipment specifications (diameter, thickness, bevel
angle) are **not yet standardized (draft)**. The engine currently assumes a 7.5 cm radius and a
6-degree bevel, which are placeholders, not measurements.

## 2. The pitch and teams

- A flat football field, 105 m long and 68 m wide, with a marked center line. No goals, no keepers.
- Two teams, Team A (left half) and Team B (right half). **Six players a side (draft).**
- No player may cross the center line. Players move freely inside their own half.

## 3. Serving

- A serve is rolled from a crouch, at ground level (launch height Z = 0), end over end, with the
  disc standing on its edge.
- A team serves from **anywhere in its own half**. After a point, the player who picks up the
  disc serves from where they picked it up.
- The team that just conceded serves next.
- A serve must cross the center line. A serve that dies in the server's own half is a point against
  the server. There is no re-do.

## 4. Play

- The disc stays live while it is upright. Players strike it back and forth with sticks.
- The nearest player on each side chases the ball; the chaser changes automatically.
- A strike's power depends on how long the player held the power bar before releasing it. A harder
  strike is less accurate **(draft)**.
- A ball may only be struck while it is on the striker's own side of the center line **(draft)**.
- A team may not strike twice in a row until the ball has crossed the center line **(draft)**.
- A swing can mishit: the ball dribbles off weakly in the wrong direction. This happens more often when the player is tired or the ball is moving fast **(draft)**.

## 4a. Rotation and the long hit (both draft)

- **Rotation:** after a point, the team that conceded rotates positions: every player moves to the next
  position slot (volleyball style) and walks there during the pickup. The other team stays put. Can be switched off.
- **Long hit:** a strike with the power bar at 90% or more (adjustable) sends the disc deep into the opponent's
  end, aimed to die about 10 m short of their baseline. It is a little less accurate and costs the striker extra
  stamina.

## 5. Scoring

- When the disc loses speed, wobbles and falls flat on its side, the play is dead. The point is
  recorded **against the side of the field it fell on**.
- A disc that leaves the pitch also counts against the side it left on.
- Play stops, the timer freezes, and the conceding team picks up the disc by hand and serves.

## 6. Time

- A match lasts up to 15 minutes (default 15). Longer settings are capped at 15.
- The clock runs only while the disc is live. It stops during pickups.
- If the score is tied at 00:00, it is **sudden death**: the next point wins. If one team leads at
  00:00, that team wins immediately **(draft)**.

## Open questions (to settle by watching real games)

- A disc that goes out over the far baseline currently counts against the side it left on, so a plain over-hit
  would score for the hitter. The long hit is built to land short of the baseline to avoid this. Should an ordinary
  over-hit instead count against the hitter's own side?
- Rotation: should the team that scored rotate too? Should rotation also swap tired players for rested ones?

- How many players a side? How long should a match be?
- Can a player strike twice in a row? Is there a limit on touches?
- What happens when a disc leaves the pitch: a point, a re-serve, or a bounce back?
- Should a leading team win at once when time runs out, or only after the current rally?
- Real equipment dimensions and the real bevel angle.
- Local terms in Hausa for each part of the game.
