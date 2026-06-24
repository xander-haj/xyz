/*
 * src/rumble.h - Portable rumble event requests.
 *
 * Gameplay code calls these functions to describe feedback-worthy events.
 * The platform host owns the actual controller/haptic hardware.
 */
#ifndef ZELDA3_RUMBLE_H_
#define ZELDA3_RUMBLE_H_

void Rumble_RequestDamageBuzz(void);
void Rumble_RequestDashStepBuzz(void);
void Rumble_RequestDashBonkBuzz(void);
void Rumble_RequestDashAttackBuzz(void);
void Rumble_RequestLandingBuzz(void);
void Rumble_RequestBombExplosionBuzz(void);
void Rumble_RequestHammerBuzz(void);
void Rumble_RequestLampFlameBuzz(void);
void Rumble_RequestBushSlashBuzz(void);
void Rumble_RequestBushThrownHitBuzz(void);
void Rumble_RequestPotBreakBuzz(void);
void Rumble_RequestMagicPowderDamageBuzz(void);
void Rumble_RequestMagicPowderTransformBuzz(void);
void Rumble_RequestSpinChargeBuildBuzz(void);
void Rumble_RequestSpinChargeReadyBuzz(void);
void Rumble_RequestSpinChargeHoldBuzz(void);
void Rumble_RequestSpinAttackStartBuzz(void);
void Rumble_RequestSpinAttackSweepBuzz(void);
void Rumble_RequestEtherStartBuzz(void);
void Rumble_RequestEtherLightningBuzz(void);
void Rumble_RequestEtherPulseBuzz(void);
void Rumble_RequestEtherExpandBuzz(void);
void Rumble_RequestEtherSpinBuzz(void);
void Rumble_RequestEtherFadeBuzz(void);
void Rumble_RequestBombosStartBuzz(void);
void Rumble_RequestBombosColumnBuzz(void);
void Rumble_RequestBombosBlastBuzz(void);
void Rumble_RequestQuakeStartBuzz(void);
void Rumble_RequestQuakePulseBuzz(void);

#endif  // ZELDA3_RUMBLE_H_
