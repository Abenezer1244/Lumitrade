import { formatPrice } from "@/lib/formatters";
interface Props { price: string | number; pair?: string }
export default function PriceDisplay({ price, pair }: Props) {
  return <span className="font-mono text-sm text-primary">{formatPrice(price, pair)}</span>;
}
