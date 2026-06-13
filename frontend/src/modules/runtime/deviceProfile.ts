/**
 * Proyecto: InfoMatt360
 * Modulo: Device Profile
 * Responsabilidad: Detectar capacidad aproximada del dispositivo para ajustar el Runtime.
 */

export type RuntimeMode = 'low' | 'balanced' | 'fast';

export type DeviceProfile = {
  mode: RuntimeMode;
  memoryGb: number;
  cpuCores: number;
  repeatWindowSize: number;
};

export function detectDeviceProfile(): DeviceProfile {
  const navigatorInfo = navigator as Navigator & { deviceMemory?: number };
  const memoryGb = navigatorInfo.deviceMemory ?? 2;
  const cpuCores = navigator.hardwareConcurrency ?? 2;

  if (memoryGb <= 2 || cpuCores <= 2) {
    return { mode: 'low', memoryGb, cpuCores, repeatWindowSize: 5 };
  }

  if (memoryGb <= 4 || cpuCores <= 4) {
    return { mode: 'balanced', memoryGb, cpuCores, repeatWindowSize: 12 };
  }

  return { mode: 'fast', memoryGb, cpuCores, repeatWindowSize: 25 };
}
