export function fastVariant(family) {
  return family.variants.find((v) => v.fast) ?? family.variants[0]
}

export function slowVariant(family) {
  return family.variants.find((v) => !v.fast) ?? family.variants[family.variants.length - 1]
}
