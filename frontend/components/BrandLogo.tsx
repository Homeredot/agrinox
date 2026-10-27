type BrandLogoProps = {
  className?: string;
  markClassName?: string;
  compact?: boolean;
};

export function BrandMark({ className = "" }: { className?: string }) {
  return <svg viewBox="0 0 48 48" role="img" aria-label="Agrinox" className={className}>
    <rect x="1" y="1" width="46" height="46" rx="13" fill="#143c2a"/>
    <rect x="1.75" y="1.75" width="44.5" height="44.5" rx="12.25" fill="none" stroke="#79bf61" strokeWidth="1.5"/>
    <path d="M10.5 35.5 21.8 11.8a2.45 2.45 0 0 1 4.4 0l11.3 23.7" fill="none" stroke="#f2f1e8" strokeWidth="4.6" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M15.2 29.2h17.6" fill="none" stroke="#9bd06c" strokeWidth="4" strokeLinecap="round"/>
    <path d="M10.8 39.1c8-4.8 18.4-4.8 26.4 0" fill="none" stroke="#5b9d51" strokeWidth="2.4" strokeLinecap="round"/>
    <circle cx="24" cy="19.3" r="2.8" fill="#e2b54c"/>
  </svg>;
}

export default function BrandLogo({ className = "", markClassName = "h-10 w-10", compact = false }: BrandLogoProps) {
  return <span className={`inline-flex min-w-0 items-center gap-2.5 ${className}`}>
    <BrandMark className={`shrink-0 ${markClassName}`}/>
    {!compact && <span className="whitespace-nowrap text-[1.05rem] font-bold tracking-[-0.035em]"><span>Agri</span><span className="text-[#88c969]">nox</span></span>}
  </span>;
}
