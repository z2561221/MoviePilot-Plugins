// 旧配置只在新字段缺失时迁移，避免覆盖用户已关闭的周期或通知。
export function migrateCleanupConfig(config) {
  const result = config && typeof config === 'object' && !Array.isArray(config) ? { ...config } : {}
  for (const prefix of ['scan', 'cleanup']) {
    for (const legacy of ['enabled', 'cron', 'notify']) {
      const key = `${prefix}_${legacy}`
      if (!(key in result) && legacy in result) result[key] = result[legacy]
    }
  }
  for (const legacy of ['enabled', 'cron', 'notify']) delete result[legacy]
  return result
}
