import React from "react";

interface VersionData {
  data: {
    version: string;
    date?: string;
  };
}

interface ChangelogStatsProps {
  versions: VersionData[];
}

const ChangelogStats: React.FC<ChangelogStatsProps> = ({ versions }) => {
  const latestVersion = versions[0];
  const totalReleases = versions.length;

  // Calculate days since latest release
  const getDaysSinceLatestRelease = (): number => {
    if (!latestVersion?.data.date) return 0;
    const latestDate = new Date(latestVersion.data.date);
    const now = new Date();
    const diffTime = Math.abs(now.getTime() - latestDate.getTime());
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  };

  const daysSinceRelease = getDaysSinceLatestRelease();

  // Format days ago display
  const formatDaysAgo = (days: number): string => {
    if (days === 0) return "Today";
    if (days === 1) return "Yesterday";
    return `${days}`;
  };

  const formatDaysLabel = (days: number): string => {
    if (days === 0) return "Released";
    if (days === 1) return "Day Ago";
    return "Days Ago";
  };

  return (
    <div className="changelog-stats">
      <div className="stat-item">
        <span className="stat-number">
          {latestVersion?.data.version || "0.0.0"}
        </span>
        <span className="stat-label">Latest Version</span>
      </div>
      <div className="stat-item">
        <span className="stat-number">{totalReleases}</span>
        <span className="stat-label">Releases</span>
      </div>
      <div className="stat-item">
        <span className="stat-number">{formatDaysAgo(daysSinceRelease)}</span>
        <span className="stat-label">{formatDaysLabel(daysSinceRelease)}</span>
      </div>
    </div>
  );
};

export default ChangelogStats;
