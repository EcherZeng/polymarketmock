import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

interface PolymarketEmbedProps {
  slug: string
}

export default function PolymarketEmbed({ slug }: PolymarketEmbedProps) {
  const src = `https://embed.polymarket.com/market?market=${encodeURIComponent(slug)}&liveactivity=true&border=true&height=300`

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">Polymarket Live</CardTitle>
      </CardHeader>
      <CardContent>
        <iframe
          title="Polymarket Embed"
          src={src}
          className="w-full rounded-md"
          height={300}
          frameBorder="0"
          allowTransparency
        />
      </CardContent>
    </Card>
  )
}
