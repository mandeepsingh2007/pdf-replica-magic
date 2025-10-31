interface SectionHeaderProps {
  title: string;
  subtitle?: string;
}

export const SectionHeader = ({ title, subtitle }: SectionHeaderProps) => {
  return (
    <div className="bg-primary text-primary-foreground py-8 px-8">
      <h2 className="text-4xl font-bold mb-2">{title}</h2>
      {subtitle && <p className="text-lg">{subtitle}</p>}
    </div>
  );
};
