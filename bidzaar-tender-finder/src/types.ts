export type TenderListItem = {
  title: string;
  url: string;
  publishedAt?: Date;
  tenderNumber?: string;
};

export type TenderDocument = {
  name: string;
  url?: string;
  localPath?: string;
  downloadedOk?: boolean;
  error?: string;
};

export type TenderDetails = {
  url: string;
  title?: string;
  tenderNumber?: string;
  organizer?: string;
  descriptionText?: string;
  publishedAt?: Date;
  deadlineAt?: Date;
  documents: TenderDocument[];
};

export type RunMeta = {
  startedAt: string;
  finishedAt?: string;
  lastRunAt?: string;
  newCount?: number;
  errors: { where: string; message: string; url?: string }[];
};

